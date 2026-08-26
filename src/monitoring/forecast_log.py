from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.utils.aqi_bands import aqi_category
from src.utils.config import get_project_root, load_config
from src.utils.metrics import regression_metrics
from src.utils.storage import load_features

def _monitor_cfg(config: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = config or load_config()
    return cfg.get("monitoring") or {}

def forecast_log_path(config: dict[str, Any] | None = None) -> Path:
    cfg = config or load_config()
    rel = _monitor_cfg(cfg).get("log_path", "artifacts/monitoring/forecast_log.parquet")
    path = get_project_root() / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    return path

def summary_path(config: dict[str, Any] | None = None) -> Path:
    cfg = config or load_config()
    rel = _monitor_cfg(cfg).get("summary_path", "artifacts/monitoring/summary.json")
    path = get_project_root() / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    return path

def load_forecast_log(config: dict[str, Any] | None = None) -> pd.DataFrame:
    path = forecast_log_path(config)
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)

def save_forecast_log(df: pd.DataFrame, config: dict[str, Any] | None = None) -> Path:
    path = forecast_log_path(config)
    out = df.copy()
    if not out.empty:
        out = out.drop_duplicates(
            subset=["city", "issued_at", "horizon_hours"],
            keep="last",
        ).sort_values(["issued_at", "city", "horizon_hours"])
    out.to_parquet(path, index=False)
    return path

def append_forecast_rows(rows: list[dict[str, Any]], config: dict[str, Any] | None = None) -> Path:
    existing = load_forecast_log(config)
    incoming = pd.DataFrame(rows)
    if existing.empty:
        combined = incoming
    else:
        combined = pd.concat([existing, incoming], ignore_index=True)
    return save_forecast_log(combined, config)

def log_live_forecasts(config: dict[str, Any] | None = None) -> dict[str, Any]:
    from src.inference.predict import predict_city

    cfg = config or load_config()
    issued_at = datetime.now(timezone.utc).isoformat()
    rows: list[dict[str, Any]] = []
    for city in cfg["cities"]:
        name = city["name"]
        try:
            pred = predict_city(name, cfg)
        except Exception as exc:
            print(f"[monitor] skip {name}: {exc}")
            continue
        issued = pred.get("event_time") or issued_at
        for item in pred["forecast"]:
            horizon = int(item["horizon_hours"])
            target_time = pd.to_datetime(issued, utc=True) + pd.Timedelta(hours=horizon)
            rows.append(
                {
                    "city": name,
                    "issued_at": str(issued),
                    "target_time": target_time.isoformat(),
                    "horizon_hours": horizon,
                    "predicted_aqi": float(item["aqi"]),
                    "aqi_low": item.get("aqi_low"),
                    "aqi_high": item.get("aqi_high"),
                    "predicted_category": item.get("category"),
                    "model": item.get("model") or pred.get("model"),
                    "actual_aqi": np.nan,
                    "actual_category": None,
                    "abs_error": np.nan,
                    "category_hit": np.nan,
                    "scored_at": None,
                    "source": "live",
                }
            )
    path = append_forecast_rows(rows, cfg)
    return {"logged": len(rows), "path": str(path)}

def reconcile_with_actuals(config: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = config or load_config()
    log = load_forecast_log(cfg)
    if log.empty:
        return {"scored": 0, "pending": 0}

    features = load_features(cfg)
    if features.empty:
        return {"scored": 0, "pending": int(len(log)), "error": "no features"}

    features = features.copy()
    features["event_time"] = pd.to_datetime(features["event_time"], utc=True)
    feat_idx = features.set_index(["city", "event_time"])["aqi"]

    log = log.copy()
    log["issued_at"] = pd.to_datetime(log["issued_at"], utc=True, format="mixed")
    log["target_time"] = pd.to_datetime(log["target_time"], utc=True, format="mixed")
    now = pd.Timestamp.now(tz="UTC")
    scored = 0
    pending = 0

    for i, row in log.iterrows():
        if pd.notna(row.get("actual_aqi")):
            continue
        if row["target_time"] > now:
            pending += 1
            continue
        key = (row["city"], row["target_time"])
        actual = None
        try:
            if key in feat_idx.index:
                actual = feat_idx.loc[key]
                if isinstance(actual, pd.Series):
                    actual = actual.iloc[-1]
        except Exception:
            actual = None
        if actual is None or (isinstance(actual, float) and pd.isna(actual)):
            city_times = features.loc[features["city"] == row["city"], "event_time"]
            if len(city_times):
                deltas = (city_times - row["target_time"]).abs()
                j = deltas.idxmin()
                if deltas.loc[j] <= pd.Timedelta(minutes=90):
                    actual = features.loc[j, "aqi"]

        if actual is None or pd.isna(actual):
            pending += 1
            continue

        actual_f = float(actual)
        pred = float(row["predicted_aqi"])
        log.at[i, "actual_aqi"] = actual_f
        log.at[i, "actual_category"] = aqi_category(actual_f)
        log.at[i, "abs_error"] = abs(actual_f - pred)
        log.at[i, "category_hit"] = float(aqi_category(actual_f) == aqi_category(pred))
        log.at[i, "scored_at"] = now.isoformat()
        scored += 1

    log["issued_at"] = log["issued_at"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    log["target_time"] = log["target_time"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    save_forecast_log(log, cfg)
    summary = build_monitoring_summary(cfg)
    return {"scored": scored, "pending": pending, "summary": summary}

def seed_historical_scores(config: dict[str, Any] | None = None) -> dict[str, Any]:
    from src.inference.predict import load_winner

    cfg = config or load_config()
    mon = _monitor_cfg(cfg)
    sample_hours = int(mon.get("backfill_sample_hours", 6))
    lookback_days = int(mon.get("backfill_score_days", 60))

    df = load_features(cfg)
    if df.empty:
        return {"seeded": 0, "error": "no features"}

    bundle = load_winner(cfg)
    if bundle["type"] != "per_horizon":
        return {"seeded": 0, "error": "per-horizon models required"}

    df = df.copy()
    df["event_time"] = pd.to_datetime(df["event_time"], utc=True)
    cutoff = df["event_time"].max() - pd.Timedelta(days=lookback_days)
    max_h = max(cfg["horizons_hours"])
    end_cut = df["event_time"].max() - pd.Timedelta(hours=max_h)
    scored_at = datetime.now(timezone.utc).isoformat()

    rows: list[dict[str, Any]] = []
    for city, city_df in df.groupby("city"):
        city_df = city_df.sort_values("event_time").reset_index(drop=True)
        sample = city_df[(city_df["event_time"] >= cutoff) & (city_df["event_time"] <= end_cut)]
        if sample.empty:
            continue
        sample = (
            sample.set_index("event_time")
            .resample(f"{sample_hours}h")
            .first()
            .dropna(subset=["aqi"])
            .reset_index()
        )
        if sample.empty:
            continue

        time_to_aqi = city_df.set_index("event_time")["aqi"]

        for h, item in bundle["models"].items():
            if item["type"] != "sklearn":
                continue
            h_meta = item["meta"]
            feature_cols = h_meta["feature_cols"]
            target_times = sample["event_time"] + pd.Timedelta(hours=int(h))
            actuals = target_times.map(time_to_aqi)
            valid = actuals.notna()
            if not valid.any():
                continue

            issued = sample.loc[valid, "event_time"].reset_index(drop=True)
            actual_vals = actuals.loc[valid].astype(float).reset_index(drop=True)
            feat = sample.loc[valid, :].reset_index(drop=True)

            X = pd.DataFrame({"city": [city] * len(feat)})
            for c in feature_cols:
                X[c] = pd.to_numeric(feat[c], errors="coerce") if c in feat.columns else 0.0
            X[feature_cols] = X[feature_cols].fillna(0)

            preds = np.asarray(item["model"].predict(X[["city", *feature_cols]]), dtype=float).reshape(-1)
            preds = np.clip(preds, 0, None)

            for i in range(len(preds)):
                pred = float(preds[i])
                actual = float(actual_vals.iloc[i])
                rows.append(
                    {
                        "city": city,
                        "issued_at": issued.iloc[i].isoformat(),
                        "target_time": (issued.iloc[i] + pd.Timedelta(hours=int(h))).isoformat(),
                        "horizon_hours": int(h),
                        "predicted_aqi": pred,
                        "aqi_low": None,
                        "aqi_high": None,
                        "predicted_category": aqi_category(pred),
                        "model": h_meta["name"],
                        "actual_aqi": actual,
                        "actual_category": aqi_category(actual),
                        "abs_error": abs(actual - pred),
                        "category_hit": float(aqi_category(actual) == aqi_category(pred)),
                        "scored_at": scored_at,
                        "source": "historical_seed",
                    }
                )

    path = append_forecast_rows(rows, cfg)
    summary = build_monitoring_summary(cfg)
    return {"seeded": len(rows), "path": str(path), "summary": summary}

def build_monitoring_summary(config: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = config or load_config()
    log = load_forecast_log(cfg)
    scored = log[log["actual_aqi"].notna()].copy() if not log.empty else pd.DataFrame()

    summary: dict[str, Any] = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "total_rows": int(len(log)) if not log.empty else 0,
        "scored_rows": int(len(scored)),
        "pending_rows": int((~log["actual_aqi"].notna()).sum()) if not log.empty else 0,
        "overall": None,
        "by_horizon": {},
        "by_city": {},
        "recent": [],
    }

    if scored.empty:
        summary_path(cfg).write_text(json.dumps(summary, indent=2), encoding="utf-8")
        return summary

    summary["overall"] = {
        **regression_metrics(scored["actual_aqi"], scored["predicted_aqi"]),
        "category_accuracy": float(scored["category_hit"].mean()),
        "mean_abs_error": float(scored["abs_error"].mean()),
    }

    for h, g in scored.groupby("horizon_hours"):
        summary["by_horizon"][str(int(h))] = {
            **regression_metrics(g["actual_aqi"], g["predicted_aqi"]),
            "category_accuracy": float(g["category_hit"].mean()),
            "n": int(len(g)),
        }

    for city, g in scored.groupby("city"):
        summary["by_city"][str(city)] = {
            "mae": float(g["abs_error"].mean()),
            "category_accuracy": float(g["category_hit"].mean()),
            "n": int(len(g)),
        }

    recent = scored.sort_values("target_time", ascending=False).head(30)
    summary["recent"] = [
        {
            "city": r["city"],
            "horizon_hours": int(r["horizon_hours"]),
            "issued_at": str(r["issued_at"]),
            "target_time": str(r["target_time"]),
            "predicted_aqi": round(float(r["predicted_aqi"]), 1),
            "actual_aqi": round(float(r["actual_aqi"]), 1),
            "abs_error": round(float(r["abs_error"]), 1),
            "category_hit": bool(r["category_hit"]),
            "predicted_category": r.get("predicted_category"),
            "actual_category": r.get("actual_category"),
        }
        for _, r in recent.iterrows()
    ]

    summary_path(cfg).write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary

def get_monitoring_summary(config: dict[str, Any] | None = None) -> dict[str, Any]:
    path = summary_path(config)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return build_monitoring_summary(config)
