
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.utils.config import get_project_root, load_config
from src.utils.storage import (
    get_hopsworks_project,
    load_features_local,
    local_feature_path,
    resolve_storage_mode,
    save_features,
)

def sync_features() -> dict:
    config = load_config()
    path = local_feature_path(config)
    if not path.exists():
        raise FileNotFoundError(f"No local features at {path}. Run backfill first.")

    df = load_features_local(config)
    print(f"[hopsworks] Local features: {len(df)} rows, {len(df.columns)} cols")
    print(f"[hopsworks] Cities: {sorted(df['city'].unique())}")

    if resolve_storage_mode(config) != "hopsworks":
        print("[hopsworks] Warning: STORAGE_MODE is not hopsworks")

    result = save_features(df, config)
    print(f"[hopsworks] Feature sync result: {result}")
    return result

def register_models(config: dict | None = None) -> dict:
    cfg = config or load_config()
    root = get_project_root()
    model_dir = root / cfg["storage"]["model_dir"]
    winner_path = model_dir / "winner.json"
    if not winner_path.exists():
        raise FileNotFoundError("No winner.json — run training_pipeline.py first.")

    meta = json.loads(winner_path.read_text(encoding="utf-8"))
    metrics = meta.get("test_metrics", {}).get("overall") or meta.get("val_metrics", {}).get("overall", {})
    description = (
        f"Per-horizon AQI forecast ({meta.get('name')}). "
        f"1-year training, realistic_mode={meta.get('realistic_mode', True)}. "
        f"Horizons: {meta.get('horizons_hours', [24, 48, 72])}."
    )

    project = get_hopsworks_project(cfg)
    mr = project.get_model_registry()
    model = mr.python.create_model(
        name=cfg["model_name"],
        metrics=metrics,
        description=description,
    )
    model.save(str(model_dir))
    version = getattr(model, "version", None)
    print(f"[hopsworks] Model registered: {cfg['model_name']} v{version}")
    return {
        "registered": True,
        "name": cfg["model_name"],
        "version": version,
        "metrics": metrics,
        "winner": meta.get("name"),
    }

def verify_hopsworks(config: dict | None = None) -> dict:
    cfg = config or load_config()
    project = get_hopsworks_project(cfg)
    fs = project.get_feature_store()
    fg_name = cfg["feature_group_name"]
    fg_version = cfg.get("feature_group_version", 3)

    out: dict = {"project": project.name, "feature_group": {}, "model_registry": {}}
    try:
        fg = fs.get_feature_group(fg_name, version=fg_version)
        out["feature_group"] = {
            "name": fg_name,
            "version": fg_version,
            "online_enabled": getattr(fg, "online_enabled", None),
        }
        try:
            offline = fg.read()
            out["feature_group"]["offline_rows"] = 0 if offline is None else len(offline)
        except Exception as exc:
            out["feature_group"]["offline_error"] = str(exc)[:200]
        try:
            online = fg.read(online=True)
            out["feature_group"]["online_rows"] = 0 if online is None else len(online)
        except Exception as exc:
            out["feature_group"]["online_error"] = str(exc)[:200]
    except Exception as exc:
        out["feature_group"]["error"] = str(exc)[:200]

    try:
        mr = project.get_model_registry()
        model = mr.get_model(cfg["model_name"], version=1)
        out["model_registry"] = {
            "name": cfg["model_name"],
            "version": getattr(model, "version", 1),
            "description": getattr(model, "description", None),
        }
    except Exception as exc:
        out["model_registry"]["error"] = str(exc)[:200]

    report_path = get_project_root() / "artifacts" / "hopsworks_verify.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"[hopsworks] Verification: {report_path}")
    print(json.dumps(out, indent=2))
    return out

def run_sync(register: bool = True, verify: bool = True) -> dict:
    config = load_config()
    if resolve_storage_mode(config) != "hopsworks":
        raise RuntimeError(
            "Set STORAGE_MODE=hopsworks and HOPSWORKS_API_KEY in .env before running hopsworks_sync."
        )

    result: dict = {"features": None, "registry": None, "verify": None}
    result["features"] = sync_features()
    if register:
        result["registry"] = register_models(config)
    if verify:
        result["verify"] = verify_hopsworks(config)

    status_path = get_project_root() / "artifacts" / "hopsworks_sync_status.json"
    status_path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    return result

def main() -> None:
    parser = argparse.ArgumentParser(description="Sync features and models to Hopsworks")
    parser.add_argument("--features-only", action="store_true")
    parser.add_argument("--models-only", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()

    config = load_config()
    if args.verify_only:
        verify_hopsworks(config)
        return
    if args.features_only:
        sync_features()
        verify_hopsworks(config)
        return
    if args.models_only:
        register_models(config)
        verify_hopsworks(config)
        return
    run_sync()

if __name__ == "__main__":
    main()
