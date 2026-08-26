
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.features.engineering import engineer_features, raw_like_frame
from src.training.models import (
    build_sklearn_models,
    prepare_supervised,
    time_based_split,
    train_lstm_model,
    train_sklearn_model,
)
from src.utils.config import get_project_root, load_config
from src.utils.metrics import average_horizon_metrics
from src.utils.storage import load_features, resolve_storage_mode, save_features_local

def _refresh_features(config: dict) -> pd.DataFrame:
    df = load_features(config)
    if df.empty:
        raise RuntimeError("No features found. Run backfill or feature_pipeline first.")
    rawish = raw_like_frame(df)
    print(f"[train] Re-engineering features from {len(rawish)} raw-like rows...")
    features = engineer_features(
        rawish,
        horizons_hours=config["horizons_hours"],
        lag_hours=config["lag_hours"],
        rolling_windows_hours=config["rolling_windows_hours"],
    )
    path = save_features_local(features, config)
    print(
        f"[train] Saved refreshed features locally: {path} "
        f"({len(features)} rows, {len(features.columns)} cols)"
    )
    return features

def _compute_shap(best: dict, splits: dict, feature_cols: list[str], out_path: Path) -> dict:
    result = {"available": False}
    if best.get("type") != "sklearn":
        out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        return result

    pipe = best["model"]
    model = pipe.named_steps["model"]
    preprocess = pipe.named_steps["preprocess"]
    X_sample = splits["X_val"][["city", *feature_cols]].head(200)
    Xt = preprocess.transform(X_sample)
    if hasattr(Xt, "toarray"):
        Xt = Xt.toarray()
    Xt = np.asarray(Xt, dtype=float)

    estimator = model.estimators_[0] if hasattr(model, "estimators_") else model
    try:
        names = list(preprocess.get_feature_names_out())
    except Exception:
        names = [f"f{i}" for i in range(Xt.shape[1])]

    try:
        if hasattr(estimator, "feature_importances_"):
            importances = np.asarray(estimator.feature_importances_, dtype=float)
            ranking = sorted(
                [{"feature": n, "importance": float(v)} for n, v in zip(names, importances)],
                key=lambda x: x["importance"],
                reverse=True,
            )[:20]
            result = {
                "available": True,
                "method": "native_feature_importances",
                "top_features": ranking,
                "model": best["name"],
            }
        elif hasattr(estimator, "coef_"):
            coefs = np.asarray(estimator.coef_, dtype=float).ravel()
            ranking = sorted(
                [{"feature": n, "importance": float(abs(v))} for n, v in zip(names, coefs)],
                key=lambda x: x["importance"],
                reverse=True,
            )[:20]
            result = {
                "available": True,
                "method": "absolute_coefficients",
                "top_features": ranking,
                "model": best["name"],
            }
        else:
            try:
                import shap
            except Exception as exc:
                result = {"available": False, "error": f"shap not installed: {exc}"}
                out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
                return result

            background = shap.sample(Xt, min(50, len(Xt)))
            explainer = shap.Explainer(estimator.predict, background)
            shap_values = explainer(Xt[:80])
            values = np.abs(np.asarray(shap_values.values)).mean(axis=0)
            ranking = sorted(
                [{"feature": n, "importance": float(v)} for n, v in zip(names, values)],
                key=lambda x: x["importance"],
                reverse=True,
            )[:20]
            result = {
                "available": True,
                "method": "shap",
                "top_features": ranking,
                "model": best["name"],
            }
    except Exception as exc:
        result = {"available": False, "error": str(exc)}

    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result

def _register_hopsworks(best_name: str, metrics: dict, model_dir: Path, config: dict) -> dict:
    try:
        from src.utils.storage import get_hopsworks_project

        project = get_hopsworks_project(config)
        mr = project.get_model_registry()
        model = mr.python.create_model(
            name=config["model_name"],
            metrics=metrics.get("overall", metrics),
            description=f"Best AQI 3-day forecast model ({best_name})",
        )
        model.save(str(model_dir))
        return {"registered": True, "name": config["model_name"]}
    except Exception as exc:
        return {"registered": False, "error": str(exc)}

def _aggregate_model_board(per_model: dict[str, dict]) -> list[dict]:
    board = []
    for name, payload in per_model.items():
        val_ph = payload["val_per_horizon"]
        test_ph = payload["test_per_horizon"]
        board.append(
            {
                "name": name,
                "type": payload["type"],
                "val": {
                    "overall": average_horizon_metrics(val_ph),
                    "per_horizon": val_ph,
                },
                "test": {
                    "overall": average_horizon_metrics(test_ph),
                    "per_horizon": test_ph,
                },
            }
        )
    board.sort(key=lambda r: r["val"]["overall"]["rmse"])
    return board

def run_training(skip_lstm: bool = False, lstm_epochs: int = 12, refresh_features: bool = True) -> dict:
    config = load_config()
    root = get_project_root()
    artifacts = root / "artifacts"
    model_dir = root / config["storage"]["model_dir"]
    artifacts.mkdir(parents=True, exist_ok=True)
    model_dir.mkdir(parents=True, exist_ok=True)

    df = _refresh_features(config) if refresh_features else load_features(config)
    if df.empty:
        raise RuntimeError("No features found. Run backfill or feature_pipeline first.")

    horizons = list(config["horizons_hours"])
    print(f"[train] Loaded {len(df)} feature rows across cities={sorted(df['city'].unique())}")
    print(f"[train] Per-horizon training for horizons={horizons}")

    per_model: dict[str, dict] = {}
    horizon_winners: dict[str, dict] = {}
    shap_source = None

    for h in horizons:
        print(f"\n[train] === Horizon +{h}h ===")
        X, y, feature_cols, targets = prepare_supervised(df, horizons, horizon_hours=h)
        splits = time_based_split(
            X,
            y,
            validation_days=config["validation_size_days"],
            test_days=config["test_size_days"],
        )
        print(
            f"[train] +{h}h split train/val/test: "
            f"{len(splits['X_train'])}/{len(splits['X_val'])}/{len(splits['X_test'])} "
            f"(features={len(feature_cols)})"
        )

        results = []
        sklearn_models = build_sklearn_models(config.get("random_seed", 42))
        for name, estimator in sklearn_models.items():
            print(f"[train] Training {name} @ {h}h...")
            res = train_sklearn_model(
                name,
                estimator,
                splits,
                feature_cols,
                targets,
                config=config,
                random_seed=config.get("random_seed", 42),
            )
            cat = res["val_metrics"]["overall"].get("category_accuracy")
            cat_s = f"  catAcc={cat:.3f}" if cat is not None and cat == cat else ""
            print(f"  val RMSE={res['val_rmse']:.3f}  R2={res['val_metrics']['overall']['r2']:.3f}{cat_s}")
            results.append(res)

        if not skip_lstm:
            print(f"[train] Training lstm @ {h}h...")
            lstm_res = train_lstm_model(
                splits,
                feature_cols,
                targets,
                random_seed=config.get("random_seed", 42),
                epochs=lstm_epochs,
                config=config,
            )
            if lstm_res:
                cat = lstm_res["val_metrics"]["overall"].get("category_accuracy")
                cat_s = f"  catAcc={cat:.3f}" if cat is not None and cat == cat else ""
                print(
                    f"  val RMSE={lstm_res['val_rmse']:.3f}  "
                    f"R2={lstm_res['val_metrics']['overall']['r2']:.3f}{cat_s}"
                )
                results.append(lstm_res)
        else:
            print("[train] Skipping LSTM")

        if not results:
            raise RuntimeError(f"No models trained for horizon {h}h")

        for res in results:
            name = res["name"]
            target = targets[0]
            bucket = per_model.setdefault(
                name,
                {"type": res["type"], "val_per_horizon": {}, "test_per_horizon": {}},
            )
            bucket["val_per_horizon"][target] = res["val_metrics"]["per_horizon"][target]
            bucket["test_per_horizon"][target] = res["test_metrics"]["per_horizon"][target]

            if res["type"] == "sklearn":
                joblib.dump(res["model"], model_dir / f"{name}_{h}h.joblib")
            else:
                res["model"].save(model_dir / f"{name}_{h}h.keras")
                meta = {
                    "scaler_mean": res["scaler_mean"].tolist(),
                    "scaler_std": res["scaler_std"].tolist(),
                    "seq_len": res["seq_len"],
                    "feature_cols": res["feature_cols"],
                }
                (model_dir / f"{name}_{h}h_meta.json").write_text(json.dumps(meta), encoding="utf-8")

        best = min(results, key=lambda r: r["val_rmse"])
        print(f"[train] Best @ {h}h: {best['name']} (val RMSE={best['val_rmse']:.3f})")
        if best.get("persistence_baseline"):
            b = best["persistence_baseline"]["val"]
            print(
                f"[train] Persistence baseline @ {h}h: "
                f"RMSE={b['rmse']:.3f} R2={b['r2']:.3f} catAcc={b.get('category_accuracy', float('nan')):.3f}"
            )

        h_key = str(h)
        horizon_winners[h_key] = {
            "horizon_hours": h,
            "name": best["name"],
            "type": best["type"],
            "feature_cols": feature_cols,
            "targets": targets,
            "val_metrics": best["val_metrics"],
            "test_metrics": best["test_metrics"],
            "prediction_interval": best.get("prediction_interval"),
            "persistence_baseline": best.get("persistence_baseline"),
        }

        if best["type"] == "sklearn":
            joblib.dump(best["model"], model_dir / f"winner_{h}h.joblib")
        else:
            best["model"].save(model_dir / f"winner_{h}h.keras")
            meta = {
                "scaler_mean": best["scaler_mean"].tolist(),
                "scaler_std": best["scaler_std"].tolist(),
                "seq_len": best["seq_len"],
                "feature_cols": best["feature_cols"],
            }
            (model_dir / f"winner_{h}h_lstm_meta.json").write_text(json.dumps(meta), encoding="utf-8")

        if h == horizons[0]:
            shap_source = (best, splits, feature_cols)

    board = _aggregate_model_board(per_model)
    winner_val_ph = {
        f"aqi_target_{h}h": horizon_winners[str(h)]["val_metrics"]["per_horizon"][f"aqi_target_{h}h"]
        for h in horizons
    }
    winner_test_ph = {
        f"aqi_target_{h}h": horizon_winners[str(h)]["test_metrics"]["per_horizon"][f"aqi_target_{h}h"]
        for h in horizons
    }
    composite_name = "+".join(f"{horizon_winners[str(h)]['name']}@{h}h" for h in horizons)
    trained_at = datetime.now(timezone.utc).isoformat()

    winner_meta = {
        "mode": "per_horizon",
        "name": composite_name,
        "type": "per_horizon",
        "realistic_mode": bool(config.get("realistic_mode", True)),
        "horizons_hours": horizons,
        "horizon_winners": horizon_winners,
        "feature_cols": horizon_winners[str(horizons[0])]["feature_cols"],
        "targets": [f"aqi_target_{h}h" for h in horizons],
        "trained_at": trained_at,
        "val_metrics": {
            "overall": average_horizon_metrics(winner_val_ph),
            "per_horizon": winner_val_ph,
        },
        "test_metrics": {
            "overall": average_horizon_metrics(winner_test_ph),
            "per_horizon": winner_test_ph,
        },
    }
    (model_dir / "winner.json").write_text(json.dumps(winner_meta, indent=2), encoding="utf-8")
    (model_dir / "horizon_winners.json").write_text(
        json.dumps(horizon_winners, indent=2), encoding="utf-8"
    )

    primary = horizon_winners[str(horizons[0])]
    if primary["type"] == "sklearn":
        joblib.dump(
            joblib.load(model_dir / f"winner_{horizons[0]}h.joblib"),
            model_dir / "winner.joblib",
        )

    leaderboard = {
        "trained_at": trained_at,
        "mode": "per_horizon",
        "realistic_mode": bool(config.get("realistic_mode", True)),
        "winner": composite_name,
        "horizon_winners": {
            k: {
                "name": v["name"],
                "val": v["val_metrics"],
                "test": v["test_metrics"],
                "prediction_interval": v.get("prediction_interval"),
                "persistence_baseline": v.get("persistence_baseline"),
            }
            for k, v in horizon_winners.items()
        },
        "models": board,
        "composite": {
            "name": composite_name,
            "val": winner_meta["val_metrics"],
            "test": winner_meta["test_metrics"],
        },
    }
    leaderboard_path = root / config["storage"]["leaderboard_path"]
    leaderboard_path.parent.mkdir(parents=True, exist_ok=True)
    leaderboard_path.write_text(json.dumps(leaderboard, indent=2), encoding="utf-8")

    shap_path = root / config["storage"]["shap_path"]
    shap_info = {"available": False}
    if shap_source:
        shap_info = _compute_shap(*shap_source, shap_path)
    print(f"[train] SHAP available={shap_info.get('available')}")

    registry_info = {"registered": False, "mode": resolve_storage_mode(config)}
    if resolve_storage_mode(config) == "hopsworks":
        registry_info = _register_hopsworks(
            composite_name,
            winner_meta["test_metrics"]["overall"],
            model_dir,
            config,
        )
    print(f"[train] Registry: {registry_info}")
    print(
        f"[train] Composite val RMSE={winner_meta['val_metrics']['overall']['rmse']:.3f} "
        f"R2={winner_meta['val_metrics']['overall']['r2']:.3f}"
    )

    return {
        "winner": composite_name,
        "leaderboard": leaderboard,
        "registry": registry_info,
        "shap": shap_info,
    }

def main() -> None:
    parser = argparse.ArgumentParser(description="Train and evaluate AQI models")
    parser.add_argument("--skip-lstm", action="store_true")
    parser.add_argument("--lstm-epochs", type=int, default=12)
    parser.add_argument(
        "--no-refresh-features",
        action="store_true",
        help="Skip re-engineering features before training",
    )
    args = parser.parse_args()
    run_training(
        skip_lstm=args.skip_lstm,
        lstm_epochs=args.lstm_epochs,
        refresh_features=not args.no_refresh_features,
    )

if __name__ == "__main__":
    main()
