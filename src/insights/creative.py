from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.utils.aqi_bands import aqi_category, aqi_color
from src.utils.config import get_project_root

MONTH_NAMES = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
]

PEAK_SMOG_MONTHS = {10, 11, 12, 1, 2}

EXPLAIN_COPY: dict[str, dict[str, str]] = {
    "Good": {
        "headline": "Air is in a healthy range",
        "meaning": "Pollution is low. Outdoor air is generally fine for everyone.",
        "action": "Good day for outdoor activity and open windows.",
    },
    "Moderate": {
        "headline": "Acceptable for most people",
        "meaning": "Air quality is okay overall, but long outdoor workouts may bother sensitive people.",
        "action": "Normal routines are fine; ease up if you have asthma or heart/lung issues.",
    },
    "Unhealthy for Sensitive Groups": {
        "headline": "Sensitive groups should take care",
        "meaning": "Children, older adults, and people with asthma may feel effects outdoors.",
        "action": "Prefer shorter outdoor time and lighter activity for sensitive groups.",
    },
    "Unhealthy": {
        "headline": "Unhealthy for everyone",
        "meaning": "Most people may feel irritation or breathing discomfort with outdoor exertion.",
        "action": "Limit outdoor time; consider a well-fitted mask if you must go out.",
    },
    "Very Unhealthy": {
        "headline": "Very unhealthy air",
        "meaning": "Health warnings of emergency conditions — everyone is more likely to be affected.",
        "action": "Avoid outdoor activity; keep indoor air as clean as possible.",
    },
    "Hazardous": {
        "headline": "Hazardous air",
        "meaning": "Serious health risk. Outdoor exposure should be avoided.",
        "action": "Stay indoors. Seek medical help if breathing feels difficult.",
    },
    "Unknown": {
        "headline": "Air quality unknown",
        "meaning": "We don’t have a clear reading yet.",
        "action": "Check back soon for an updated forecast.",
    },
}

def explain_aqi(aqi: float | int | None, category: str | None = None) -> dict[str, Any]:
    cat = category or aqi_category(aqi)
    copy = EXPLAIN_COPY.get(cat, EXPLAIN_COPY["Unknown"])
    band = None
    from src.utils.aqi_bands import AQI_BANDS

    for b in AQI_BANDS:
        if b["name"] == cat:
            band = {"min": b["min"], "max": b["max"], "color": b["color"]}
            break
    return {
        "aqi": aqi,
        "category": cat,
        "color": aqi_color(aqi),
        "band": band,
        **copy,
    }

def exercise_advice(
    current_aqi: float | int | None,
    current_category: str | None,
    forecast_24h_aqi: float | int | None = None,
    forecast_24h_category: str | None = None,
) -> dict[str, Any]:
    aqi = float(current_aqi) if current_aqi is not None else None
    cat = current_category or aqi_category(aqi)
    fwd = float(forecast_24h_aqi) if forecast_24h_aqi is not None else None
    fwd_cat = forecast_24h_category or aqi_category(fwd)

    if aqi is None:
        return {
            "verdict": "unknown",
            "title": "Not sure yet",
            "reason": "Waiting for a live AQI reading.",
            "recommendation": "Check again in a few minutes.",
            "intensity": "none",
            "current_aqi": None,
            "forecast_24h_aqi": fwd,
        }

    effective = aqi if fwd is None else max(aqi, fwd)
    effective_cat = aqi_category(effective)

    if effective <= 50:
        verdict, title, intensity = "yes", "Yes — great for outdoor exercise", "full"
        reason = f"Air is Good now (AQI {int(round(aqi))})."
    elif effective <= 100:
        verdict, title, intensity = "yes", "Yes — outdoor exercise is fine", "full"
        reason = f"Air is Moderate (AQI {int(round(aqi))}). Most people can train outdoors."
    elif effective <= 150:
        verdict, title, intensity = "caution", "Light outdoor activity only", "light"
        reason = (
            f"Air may bother sensitive groups (now {cat}, AQI {int(round(aqi))}). "
            "Prefer shorter or gentler workouts."
        )
    elif effective <= 200:
        verdict, title, intensity = "no", "Skip outdoor exercise", "indoor"
        reason = (
            f"Air is Unhealthy (AQI {int(round(effective))}). "
            "Move your workout indoors if you can."
        )
    else:
        verdict, title, intensity = "no", "Avoid outdoor exercise", "none"
        reason = (
            f"Air is {effective_cat} (AQI {int(round(effective))}). "
            "Stay indoors and avoid exertion outside."
        )

    if fwd is not None and fwd_cat and fwd_cat != cat:
        reason += f" Outlook +24h: {fwd_cat} (AQI {int(round(fwd))})."

    return {
        "verdict": verdict,
        "title": title,
        "reason": reason,
        "recommendation": {
            "yes": "Outdoor run, walk, or sports look reasonable.",
            "caution": "Keep it light outdoors, or train indoors.",
            "no": "Choose an indoor workout today.",
            "unknown": "Check back soon.",
        }[verdict],
        "intensity": intensity,
        "current_aqi": aqi,
        "current_category": cat,
        "forecast_24h_aqi": fwd,
        "forecast_24h_category": fwd_cat,
        "effective_category": effective_cat,
    }

def smog_season_calendar(config: dict[str, Any] | None = None) -> dict[str, Any]:
    root = get_project_root()
    eda_path = root / "artifacts" / "report" / "eda_highlights.json"
    by_month: dict[str, float] = {}
    findings: list[str] = []
    date_range = None
    if eda_path.exists():
        eda = json.loads(eda_path.read_text(encoding="utf-8"))
        by_month = (eda.get("seasonality") or {}).get("by_month") or {}
        findings = eda.get("findings") or []
        date_range = eda.get("date_range")

    if not by_month:
        by_month = {
            "1": 140,
            "2": 115,
            "3": 95,
            "4": 88,
            "5": 105,
            "6": 110,
            "7": 118,
            "8": 109,
            "9": 97,
            "10": 105,
            "11": 120,
            "12": 135,
        }

    now = datetime.now(timezone.utc)
    current_month = now.month
    months = []
    values = []
    for m in range(1, 13):
        mean = float(by_month.get(str(m), by_month.get(m, 0)) or 0)
        values.append(mean)
        months.append(
            {
                "month": m,
                "label": MONTH_NAMES[m - 1],
                "mean_aqi": round(mean, 1),
                "category": aqi_category(mean),
                "color": aqi_color(mean),
                "is_peak_smog": m in PEAK_SMOG_MONTHS,
                "is_current": m == current_month,
            }
        )

    peak = max(months, key=lambda x: x["mean_aqi"])
    cleanest = min(months, key=lambda x: x["mean_aqi"])
    in_peak = current_month in PEAK_SMOG_MONTHS

    return {
        "months": months,
        "peak_smog_months": sorted(PEAK_SMOG_MONTHS),
        "peak_smog_label": "Oct – Feb",
        "current_month": current_month,
        "in_peak_season": in_peak,
        "headline": (
            "You are in Pakistan’s peak smog season"
            if in_peak
            else "Outside the peak winter smog window"
        ),
        "summary": (
            f"Highest average month: {peak['label']} (~{peak['mean_aqi']} AQI). "
            f"Cleanest: {cleanest['label']} (~{cleanest['mean_aqi']} AQI). "
            "Winter months tend to be worse across the 5 cities."
        ),
        "peak_month": peak,
        "cleanest_month": cleanest,
        "findings": findings[:3],
        "date_range": date_range,
        "source": "artifacts/report/eda_highlights.json" if eda_path.exists() else "fallback",
    }

def persistence_baseline_report(config: dict[str, Any] | None = None) -> dict[str, Any]:
    root = get_project_root()
    winner_path = root / "artifacts" / "models" / "winner.json"
    if not winner_path.exists():
        return {"available": False, "note": "Train models to populate baseline comparison."}

    winner = json.loads(winner_path.read_text(encoding="utf-8"))
    horizons = winner.get("horizon_winners") or {}
    rows = []
    mae_gains = []
    rmse_gains = []

    for h_key, meta in horizons.items():
        model_val = (meta.get("val_metrics") or {}).get("overall") or {}
        base_val = (meta.get("persistence_baseline") or {}).get("val") or {}
        if not model_val or not base_val:
            continue
        m_mae = float(model_val.get("mae") or 0)
        b_mae = float(base_val.get("mae") or 0)
        m_rmse = float(model_val.get("rmse") or 0)
        b_rmse = float(base_val.get("rmse") or 0)
        mae_improve = ((b_mae - m_mae) / b_mae) if b_mae else 0.0
        rmse_improve = ((b_rmse - m_rmse) / b_rmse) if b_rmse else 0.0
        beats = m_mae < b_mae
        mae_gains.append(mae_improve)
        rmse_gains.append(rmse_improve)
        rows.append(
            {
                "horizon_hours": int(h_key),
                "model": meta.get("name"),
                "model_mae": round(m_mae, 2),
                "baseline_mae": round(b_mae, 2),
                "mae_improvement_pct": round(mae_improve * 100, 1),
                "model_rmse": round(m_rmse, 2),
                "baseline_rmse": round(b_rmse, 2),
                "rmse_improvement_pct": round(rmse_improve * 100, 1),
                "beats_baseline": beats,
                "model_r2": round(float(model_val.get("r2") or 0), 3),
                "baseline_r2": round(float(base_val.get("r2") or 0), 3),
            }
        )

    if not rows:
        return {"available": False, "note": "No persistence baseline found in winner metadata."}

    beat_rate = sum(1 for r in rows if r["beats_baseline"]) / len(rows)
    return {
        "available": True,
        "note": "Persistence baseline = predict future AQI equals current AQI (naive).",
        "winner_model": winner.get("name"),
        "trained_at": winner.get("trained_at"),
        "horizons": rows,
        "overall": {
            "horizons_beaten": sum(1 for r in rows if r["beats_baseline"]),
            "horizons_total": len(rows),
            "beat_rate": round(beat_rate, 3),
            "avg_mae_improvement_pct": round(sum(mae_gains) / len(mae_gains) * 100, 1),
            "avg_rmse_improvement_pct": round(sum(rmse_gains) / len(rmse_gains) * 100, 1),
        },
    }

def _freshness(ts: datetime | None, ok_hours: float, warn_hours: float) -> str:
    if ts is None:
        return "red"
    age_h = (datetime.now(timezone.utc) - ts).total_seconds() / 3600
    if age_h <= ok_hours:
        return "green"
    if age_h <= warn_hours:
        return "yellow"
    return "red"

def _parse_iso(raw: Any) -> datetime | None:
    if not raw:
        return None
    try:
        ts = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts


def _winner_artifacts_present(model_dir: Path, meta: dict[str, Any]) -> bool:
    if meta.get("mode") == "per_horizon" or meta.get("type") == "per_horizon":
        winners = meta.get("horizon_winners") or {}
        if not winners:
            return False
        for h, h_meta in winners.items():
            if h_meta.get("type") == "sklearn":
                if not (model_dir / f"winner_{h}h.joblib").exists():
                    return False
            elif not (model_dir / f"winner_{h}h.keras").exists():
                return False
        return True
    if meta.get("type") == "sklearn":
        return (model_dir / "winner.joblib").exists()
    return (model_dir / "winner.keras").exists()


def pipeline_health(config: dict[str, Any] | None = None) -> dict[str, Any]:
    from src.utils.storage import load_features, local_feature_path, resolve_storage_mode

    root = get_project_root()
    cfg = config or {}
    storage = resolve_storage_mode(cfg) if cfg else "local"
    deployed = storage == "hopsworks"
    checks: list[dict[str, Any]] = []

    # --- Features: Hopsworks live data when deployed; local parquet otherwise ---
    feat_updated: datetime | None = None
    if deployed:
        feat_label = "Feature store (Hopsworks)"
        feat_status = "yellow"
        feat_detail = "Feature cache warming (loads on first forecast)"
        try:
            from src.utils.storage import _mem_features

            cached = _mem_features()
            if cached is not None and not cached.empty and "event_time" in cached.columns:
                import pandas as pd

                latest = pd.to_datetime(cached["event_time"], utc=True).max()
                feat_updated = latest.to_pydatetime()
                if feat_updated.tzinfo is None:
                    feat_updated = feat_updated.replace(tzinfo=timezone.utc)
                feat_status = _freshness(feat_updated, ok_hours=36, warn_hours=72)
                feat_detail = f"Hopsworks · {len(cached):,} rows cached · latest {feat_updated.isoformat()}"
        except Exception as exc:
            feat_status = "yellow"
            feat_detail = f"Feature cache unavailable ({type(exc).__name__})"
    else:
        features_path = local_feature_path(cfg) if cfg else root / "artifacts" / "features.parquet"
        if features_path.exists():
            feat_updated = datetime.fromtimestamp(features_path.stat().st_mtime, tz=timezone.utc)
        feat_status = _freshness(feat_updated, ok_hours=36, warn_hours=72) if feat_updated else "red"
        feat_detail = (
            f"Updated {feat_updated.isoformat()}"
            if feat_updated
            else "Features file missing — run the feature pipeline"
        )
        feat_label = "Feature store / local features"
    checks.append(
        {
            "id": "features",
            "label": feat_label,
            "status": feat_status,
            "detail": feat_detail,
            "updated_at": feat_updated.isoformat() if feat_updated else None,
        }
    )

    # --- Model: on Render, deployed winner files matter more than training age ---
    model_dir = root / "artifacts" / "models"
    winner_path = model_dir / "winner.json"
    trained_at = None
    winner_name = None
    meta: dict[str, Any] = {}
    if winner_path.exists():
        meta = json.loads(winner_path.read_text(encoding="utf-8"))
        winner_name = meta.get("name")
        trained_at = _parse_iso(meta.get("trained_at"))

    if not winner_path.exists():
        model_status = "red"
        model_detail = "No winner model registered"
    elif not _winner_artifacts_present(model_dir, meta):
        model_status = "red"
        model_detail = f"{winner_name or 'Winner'} registered but model files missing"
    elif deployed:
        # API host only gets new winner files on redeploy; don't flag age as "Needs action"
        model_status = "green"
        model_detail = f"{winner_name} · serving on API"
        if trained_at and _freshness(trained_at, ok_hours=24 * 14, warn_hours=24 * 45) == "red":
            model_status = "yellow"
            model_detail = f"{winner_name} · serving (trained {trained_at.date().isoformat()}; redeploy to refresh)"
    else:
        model_status = _freshness(trained_at, ok_hours=24 * 10, warn_hours=24 * 20) if trained_at else "red"
        model_detail = winner_name or "No winner model registered"

    checks.append(
        {
            "id": "model",
            "label": "Trained model",
            "status": model_status,
            "detail": model_detail,
            "updated_at": trained_at.isoformat() if trained_at else None,
        }
    )

    # --- Monitoring: CI/deploy snapshot on API host is expected; don't age-out as failure ---
    mon_path = root / "artifacts" / "monitoring" / "summary.json"
    mon_at = None
    mon_detail = "No monitoring summary"
    mon_status = "yellow"
    if mon_path.exists():
        mon = json.loads(mon_path.read_text(encoding="utf-8"))
        mon_at = _parse_iso(mon.get("updated_at"))
        scored = mon.get("scored_rows") or 0
        mae = (mon.get("overall") or {}).get("mae")
        mae_bit = f" · MAE {mae:.1f}" if mae is not None else ""
        if deployed:
            if scored:
                mon_status = "green"
                mon_detail = f"{scored} scored rows{mae_bit} (CI snapshot on API)"
            else:
                mon_status = "yellow"
                mon_detail = "Monitoring snapshot present but no scored rows yet"
        else:
            mon_status = _freshness(mon_at, ok_hours=36, warn_hours=72) if mon_at else "yellow"
            mon_detail = f"{scored} scored rows{mae_bit}" if scored or mae is not None else mon_detail
    elif deployed:
        mon_detail = "No monitoring snapshot on API host (hourly CI updates Hopsworks / GitHub)"
    checks.append(
        {
            "id": "monitoring",
            "label": "Live accuracy monitor",
            "status": mon_status,
            "detail": mon_detail,
            "updated_at": mon_at.isoformat() if mon_at else None,
        }
    )

    checks.append(
        {
            "id": "storage",
            "label": "Storage mode",
            "status": "green",
            "detail": storage,
            "updated_at": None,
        }
    )

    sync_path = root / "artifacts" / "hopsworks_sync_status.json"
    if sync_path.exists():
        sync = json.loads(sync_path.read_text(encoding="utf-8"))
        sync_at = _parse_iso(sync.get("synced_at") or sync.get("updated_at") or sync.get("finished_at"))
        ok = sync.get("ok") if "ok" in sync else sync.get("success", True)
        checks.append(
            {
                "id": "hopsworks",
                "label": "Hopsworks sync",
                "status": "green" if ok else "yellow",
                "detail": sync.get("message") or ("Synced" if ok else "Check sync status"),
                "updated_at": sync_at.isoformat() if sync_at else None,
            }
        )

    status_rank = {"green": 0, "yellow": 1, "red": 2}
    worst = max(checks, key=lambda c: status_rank.get(c["status"], 0))["status"]
    return {
        "overall": worst,
        "overall_label": {"green": "Healthy", "yellow": "Attention", "red": "Needs action"}[worst],
        "checks": checks,
        "storage_mode": storage,
        "winner_model": winner_name,
    }
