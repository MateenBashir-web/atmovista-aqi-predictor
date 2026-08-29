from __future__ import annotations

import gc
import os
import threading
import time
from pathlib import Path
from typing import Any

import pandas as pd

from .config import get_project_root, load_config

_FEATURES_MEM: dict[str, Any] = {}
_FEATURES_MEM_TTL_SEC = 3600.0  # features refresh hourly; keep warm between requests
_FEATURES_LOAD_LOCK = threading.Lock()
_HOPSWORKS_PROJECT = None
# Inference needs ~72h lags; 7 days of hourly rows is enough for history + forecast.
_FEATURES_KEEP_PER_CITY = 168
_SERVE_LOOKBACK_DAYS = int(os.getenv("FEATURE_SERVE_DAYS", "7"))


def _trim_features_for_serving(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty or "city" not in df.columns or "event_time" not in df.columns:
        return df
    work = df
    if not pd.api.types.is_datetime64_any_dtype(work["event_time"]):
        work = df.copy()
        work["event_time"] = pd.to_datetime(work["event_time"], utc=True)
    work = work.sort_values(["city", "event_time"])
    trimmed = work.groupby("city", group_keys=False).tail(_FEATURES_KEEP_PER_CITY)
    return trimmed.reset_index(drop=True)

def resolve_storage_mode(config: dict[str, Any] | None = None) -> str:
    mode = os.getenv("STORAGE_MODE", "auto").lower()
    if mode in {"local", "hopsworks"}:
        return mode
    return "hopsworks" if os.getenv("HOPSWORKS_API_KEY") else "local"

def local_feature_path(config: dict[str, Any] | None = None) -> Path:
    cfg = config or load_config()
    root = get_project_root()
    path = root / cfg["storage"]["local_dir"] / "aqi_features.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path

def invalidate_features_cache() -> None:
    _FEATURES_MEM.clear()

def save_features_local(df: pd.DataFrame, config: dict[str, Any] | None = None) -> Path:
    path = local_feature_path(config)
    if path.exists():
        existing = pd.read_parquet(path)
        combined = pd.concat([existing, df], ignore_index=True)
        combined = combined.drop_duplicates(subset=["city", "event_time"], keep="last")
        combined = combined.sort_values(["city", "event_time"]).reset_index(drop=True)
        combined.to_parquet(path, index=False)
    else:
        df = df.sort_values(["city", "event_time"]).reset_index(drop=True)
        df.to_parquet(path, index=False)
    invalidate_features_cache()
    return path

def load_features_local(config: dict[str, Any] | None = None) -> pd.DataFrame:
    path = local_feature_path(config)
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)

def get_hopsworks_project(config: dict[str, Any] | None = None):
    global _HOPSWORKS_PROJECT
    if _HOPSWORKS_PROJECT is not None:
        return _HOPSWORKS_PROJECT

    cfg = config or load_config()
    api_key = os.getenv("HOPSWORKS_API_KEY")
    if not api_key:
        raise RuntimeError("HOPSWORKS_API_KEY is not set")

    import hopsworks

    project_name = os.getenv("HOPSWORKS_PROJECT") or cfg["hopsworks"]["project_name"]
    host = os.getenv("HOPSWORKS_HOST") or cfg["hopsworks"].get("host") or "c.app.hopsworks.ai"
    _HOPSWORKS_PROJECT = hopsworks.login(host=host, project=project_name, api_key_value=api_key)
    return _HOPSWORKS_PROJECT

def _sync_via_hopsworks_job(project, config: dict[str, Any]) -> dict[str, Any]:
    ds = project.get_dataset_api()
    job_api = project.get_job_api()
    root = get_project_root()

    remote_data_dir = "Resources/aqi_data"
    remote_job_dir = "Resources/aqi_jobs"
    for folder in (remote_data_dir, remote_job_dir):
        try:
            ds.mkdir(folder)
        except Exception:
            pass

    local_parquet = local_feature_path(config)
    ds.upload(str(local_parquet), remote_data_dir, overwrite=True)

    local_script = root / "pipelines" / "hopsworks_insert_job.py"
    ds.upload(str(local_script), remote_job_dir, overwrite=True)

    cfg = job_api.get_configuration("PYTHON")
    cfg["appPath"] = f"/Projects/{project.name}/Resources/aqi_jobs/hopsworks_insert_job.py"
    job = job_api.create_job("aqi_feature_insert", cfg)
    execution = job.run(await_termination=True)
    state = getattr(execution, "state", None) or "FINISHED"
    return {
        "mode": "hopsworks_job",
        "feature_group": config["feature_group_name"],
        "version": config.get("feature_group_version", 2),
        "job": "aqi_feature_insert",
        "state": str(state),
        "rows_local": int(pd.read_parquet(local_parquet).shape[0]) if local_parquet.exists() else 0,
    }

def save_features(df: pd.DataFrame, config: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = config or load_config()
    mode = resolve_storage_mode(cfg)
    if mode == "local":
        path = save_features_local(df, cfg)
        return {"mode": "local", "path": str(path), "rows": len(df)}

    work = df.copy()
    if "event_time" in work.columns:
        work["event_time"] = pd.to_datetime(work["event_time"], utc=True)

    save_features_local(work, cfg)

    project = get_hopsworks_project(cfg)
    fs = project.get_feature_store()
    fg_name = cfg["feature_group_name"]
    fg_version = cfg.get("feature_group_version", 2)

    fg = fs.get_or_create_feature_group(
        name=fg_name,
        version=fg_version,
        description="Hourly AQI features and 3-day targets for Pakistan cities",
        primary_key=["city", "event_time"],
        event_time="event_time",
        online_enabled=cfg["hopsworks"].get("feature_store_online", True),
        time_travel_format="DELTA",
    )
    if fg is None:
        raise RuntimeError(f"Could not get or create feature group {fg_name}")

    try:
        fg.insert(work, write_options={"wait_for_job": False})
        _FEATURES_MEM["df"] = work
        _FEATURES_MEM["loaded_at"] = time.monotonic()
        _FEATURES_MEM["source"] = "hopsworks"
        return {"mode": "hopsworks", "feature_group": fg_name, "version": fg_version, "rows": len(work)}
    except Exception as exc:
        print(f"[storage] direct insert failed ({type(exc).__name__}): {exc}")
        print("[storage] launching Hopsworks job fallback")
        try:
            result = _sync_via_hopsworks_job(project, cfg)
            result["direct_insert_error"] = f"{type(exc).__name__}: {exc}"
            return result
        except Exception as job_exc:
            print(f"[storage] job fallback failed ({type(job_exc).__name__}): {job_exc}")
            return {
                "mode": "local_fallback",
                "path": str(local_feature_path(cfg)),
                "rows": len(work),
                "direct_insert_error": f"{type(exc).__name__}: {exc}",
                "job_fallback_error": f"{type(job_exc).__name__}: {job_exc}",
            }

def _mem_features() -> pd.DataFrame | None:
    df = _FEATURES_MEM.get("df")
    loaded_at = _FEATURES_MEM.get("loaded_at")
    if df is None or loaded_at is None:
        return None
    if time.monotonic() - float(loaded_at) > _FEATURES_MEM_TTL_SEC:
        return None
    return df

def _store_mem_features(df: pd.DataFrame, source: str) -> pd.DataFrame:
    _FEATURES_MEM["df"] = df
    _FEATURES_MEM["loaded_at"] = time.monotonic()
    _FEATURES_MEM["source"] = source
    return df

def _load_features_hopsworks(cfg: dict[str, Any]) -> pd.DataFrame:
    from datetime import datetime, timedelta, timezone

    project = get_hopsworks_project(cfg)
    fs = project.get_feature_store()
    fg = fs.get_feature_group(
        name=cfg["feature_group_name"],
        version=cfg.get("feature_group_version", 2),
    )
    errors: list[str] = []
    cutoff = datetime.now(timezone.utc) - timedelta(days=_SERVE_LOOKBACK_DAYS)

    def _try_read(label: str, reader):
        raw = reader()
        if raw is None or getattr(raw, "empty", True):
            errors.append(f"{label}: empty")
            return None
        trimmed = _trim_features_for_serving(raw)
        print(
            f"[storage] Hopsworks features via {label}: "
            f"{len(raw)} raw → {len(trimmed)} kept for serving"
        )
        del raw
        gc.collect()
        return trimmed

    # Online store is smallest — try first on the 512MB API instance.
    for label, reader in (
        ("online", lambda: fg.read(online=True)),
    ):
        try:
            got = _try_read(label, reader)
            if got is not None:
                return got
        except Exception as exc:
            errors.append(f"{label}: {type(exc).__name__}: {exc}")

    try:
        filtered = fg.filter(fg.event_time >= cutoff)
        got = _try_read("filtered_recent", filtered.read)
        if got is not None:
            return got
    except Exception as exc:
        errors.append(f"filtered_recent: {type(exc).__name__}: {exc}")

    # Never pull the full offline FG on the API — it OOMs Starter (512MB).
    raise RuntimeError("; ".join(errors) if errors else "No recent feature rows returned")

def load_features(config: dict[str, Any] | None = None) -> pd.DataFrame:
    cfg = config or load_config()
    mode = resolve_storage_mode(cfg)

    cached = _mem_features()
    if cached is not None and not cached.empty:
        return cached

    # Single-flight: avoid stampedes that crash Starter RAM / block the API.
    with _FEATURES_LOAD_LOCK:
        cached = _mem_features()
        if cached is not None and not cached.empty:
            return cached

        if mode == "hopsworks":
            try:
                df = _load_features_hopsworks(cfg)
                if not df.empty:
                    return _store_mem_features(df, "hopsworks")
            except Exception as exc:
                print(f"[storage] Hopsworks load failed ({type(exc).__name__}): {exc}")
            return pd.DataFrame()

        if mode == "local":
            df = load_features_local(cfg)
            if not df.empty:
                return _store_mem_features(_trim_features_for_serving(df), "local")
            return df

        try:
            df = _load_features_hopsworks(cfg)
            if not df.empty:
                return _store_mem_features(df, "hopsworks")
        except Exception:
            pass

        df = load_features_local(cfg)
        if not df.empty:
            return _store_mem_features(_trim_features_for_serving(df), "local")
        return df
