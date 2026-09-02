from __future__ import annotations

import json
from typing import Any

import numpy as np
import pandas as pd

from src.inference.predict import load_horizon_bundle
from src.utils.config import get_project_root, load_config
from src.utils.storage import load_features
from src.utils.timezone import latest_observed_row

FEATURE_GLOSSARY: dict[str, str] = {
    "aqi": "Current air quality index",
    "pm25": "Fine particles (PM2.5)",
    "pm10": "Coarse particles (PM10)",
    "o3": "Ozone",
    "no2": "Nitrogen dioxide (traffic/combustion)",
    "so2": "Sulfur dioxide",
    "co": "Carbon monoxide",
    "temperature_2m": "Air temperature near surface",
    "relative_humidity_2m": "Relative humidity",
    "precipitation": "Rain / precipitation",
    "wind_speed_10m": "Wind speed",
    "wind_direction_10m": "Wind direction",
    "cloud_cover": "Cloud cover",
    "surface_pressure": "Surface pressure",
    "aqi_change_rate": "Recent AQI change rate",
    "aqi_pct_change": "Percent change in AQI",
    "temp_humidity": "Temperature × humidity interaction",
    "wind_pm25": "Wind × PM2.5 interaction",
    "hour": "Hour of day",
    "day": "Day of month",
    "day_of_week": "Day of week",
    "month": "Month of year",
    "hour_sin": "Hour cyclic encoding (sin)",
    "hour_cos": "Hour cyclic encoding (cos)",
    "month_sin": "Month cyclic encoding (sin)",
    "month_cos": "Month cyclic encoding (cos)",
    "dow_sin": "Weekday cyclic encoding (sin)",
    "dow_cos": "Weekday cyclic encoding (cos)",
}

_EXPLAIN_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_COMPARE_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_EXPLAIN_TTL_SEC = 180.0
_COMPARE_TTL_SEC = 300.0


def _clean_feature_name(name: str) -> str:
    return (
        str(name)
        .replace("num__", "")
        .replace("city__", "city=")
        .replace("_fwd_", " forecast +")
        .replace("_", " ")
    )


def _glossary_entry(raw_name: str) -> str:
    key = str(raw_name).replace("num__", "").replace("city__", "")
    if key in FEATURE_GLOSSARY:
        return FEATURE_GLOSSARY[key]
    if key.startswith("aqi_lag_"):
        return f"AQI from {key.replace('aqi_lag_', '').replace('h', '')} hours ago"
    if key.startswith("pm25_lag_"):
        return f"PM2.5 from {key.replace('pm25_lag_', '').replace('h', '')} hours ago"
    if key.startswith("aqi_roll_mean_"):
        return f"Average AQI over last {key.replace('aqi_roll_mean_', '')}"
    if key.startswith("aqi_roll_std_"):
        return f"AQI variability over last {key.replace('aqi_roll_std_', '')}"
    if "fwd" in key or "forecast" in key:
        return "Future weather feature used by the model"
    if key.startswith("city="):
        return f"City indicator for {key.replace('city=', '')}"
    return _clean_feature_name(raw_name)


def _annotate_features(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for item in items:
        raw = str(item.get("feature", ""))
        contrib = float(item.get("contribution", item.get("importance", 0.0)))
        direction = "up" if contrib > 0 else "down" if contrib < 0 else "neutral"
        out.append(
            {
                **item,
                "feature": _clean_feature_name(raw)[:36],
                "raw_feature": raw,
                "contribution": round(contrib, 4),
                "importance": round(abs(contrib), 4),
                "direction": direction,
                "glossary": _glossary_entry(raw),
            }
        )
    return out


def _ranking_abs(names: list[str], values: np.ndarray, top_k: int = 12) -> list[dict[str, Any]]:
    values = np.asarray(values, dtype=float).ravel()
    pairs = [
        {"feature": str(n), "contribution": float(abs(v)), "importance": float(abs(v))}
        for n, v in zip(names, values)
    ]
    pairs.sort(key=lambda x: x["importance"], reverse=True)
    return _annotate_features(pairs[:top_k])


def _ranking_signed(names: list[str], values: np.ndarray, top_k: int = 12) -> list[dict[str, Any]]:
    values = np.asarray(values, dtype=float).ravel()
    pairs = [
        {"feature": str(n), "contribution": float(v), "importance": float(abs(v))}
        for n, v in zip(names, values)
    ]
    pairs.sort(key=lambda x: x["importance"], reverse=True)
    return _annotate_features(pairs[:top_k])


def _waterfall(local_signed: list[dict[str, Any]], base_value: float, prediction: float) -> dict[str, Any]:
    steps = []
    running = float(base_value)
    for item in local_signed[:8]:
        before = running
        running += float(item["contribution"])
        steps.append(
            {
                "feature": item["feature"],
                "raw_feature": item.get("raw_feature"),
                "contribution": item["contribution"],
                "direction": item["direction"],
                "glossary": item.get("glossary"),
                "before": round(before, 2),
                "after": round(running, 2),
            }
        )
    return {
        "base_value": round(float(base_value), 2),
        "prediction": round(float(prediction), 2),
        "steps": steps,
        "residual": round(float(prediction) - running, 2),
    }


def _narrative(city: str, horizon: int, local_signed: list[dict[str, Any]], prediction: float | None) -> str:
    if not local_signed:
        return f"No local explanation available for {city} at +{horizon}h."
    top = local_signed[:3]
    bits = []
    for item in top:
        arrow = "raises" if item["direction"] == "up" else "lowers"
        bits.append(f"{item['feature']} {arrow} the forecast")
    pred_bit = f" toward about {prediction:.0f} AQI" if prediction is not None else ""
    return (
        f"For {city} (+{horizon}h), the latest forecast is driven mainly by "
        + "; ".join(bits)
        + f"{pred_bit}."
    )


def _pollutant_link(local_signed: list[dict[str, Any]], pollutants: list[dict[str, Any]] | None) -> dict[str, Any]:
    poll_keys = {"pm25", "pm10", "o3", "no2", "so2", "co", "aqi"}
    shap_hits = []
    for item in local_signed[:8]:
        raw = str(item.get("raw_feature", "")).lower()
        for key in poll_keys:
            if key in raw.replace(" ", "").replace("_", ""):
                shap_hits.append({"feature": item["feature"], "key": key, "direction": item["direction"]})
                break
    dominant = None
    if pollutants:
        dominant = next((p for p in pollutants if p.get("is_dominant")), pollutants[0])
    agree = False
    if dominant and shap_hits:
        agree = any(dominant.get("key") in h["key"] or h["key"] in str(dominant.get("key")) for h in shap_hits)
        dkey = str(dominant.get("key", "")).lower()
        agree = agree or any(dkey in h["key"] or h["key"] in dkey for h in shap_hits)
    return {
        "shap_pollutant_features": shap_hits[:4],
        "dominant_pollutant": dominant.get("label") if dominant else None,
        "agree": agree,
        "note": (
            "SHAP drivers and live pollutant chemistry point to the same family of signals."
            if agree
            else "SHAP drivers and live pollutant chemistry may differ; model also uses lags/weather."
        ),
    }


def _load_city_slice(
    city: str,
    feature_cols: list[str],
    config: dict[str, Any],
    max_rows: int = 100,
) -> tuple[pd.DataFrame, str | None]:
    df = load_features(config)
    if df.empty:
        raise RuntimeError("No feature data available for explanations")
    city_df = df[df["city"] == city].sort_values("event_time")
    if city_df.empty:
        raise ValueError(f"No rows for city={city}")
    latest_ts = pd.to_datetime(latest_observed_row(city_df)["event_time"], utc=True).isoformat()
    frame = city_df[["city", *feature_cols]].copy()
    for col in feature_cols:
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    frame[feature_cols] = frame[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(0)
    return frame.tail(max_rows).reset_index(drop=True), latest_ts


def _shap_for_estimator(
    estimator,
    Xt_city: np.ndarray,
    Xt_latest: np.ndarray,
    feature_names: list[str],
) -> tuple[np.ndarray, np.ndarray, float, str, str]:
    import shap

    background_n = min(30, len(Xt_city))
    background = shap.sample(Xt_city, background_n) if len(Xt_city) > background_n else Xt_city
    expected = float(np.mean(estimator.predict(background)))

    if hasattr(estimator, "coef_"):
        explainer = shap.LinearExplainer(estimator, background)
        shap_city = np.asarray(explainer.shap_values(Xt_city))
        shap_local = np.asarray(explainer.shap_values(Xt_latest))
        method, local_method = "city_mean_abs_shap", "local_signed_shap"
        if hasattr(explainer, "expected_value"):
            ev = explainer.expected_value
            expected = float(np.asarray(ev).ravel()[0])
    elif hasattr(estimator, "feature_importances_"):
        explainer = shap.TreeExplainer(estimator)
        shap_city = np.asarray(explainer.shap_values(Xt_city))
        shap_local = np.asarray(explainer.shap_values(Xt_latest))
        method, local_method = "city_mean_abs_shap", "local_signed_shap"
        if hasattr(explainer, "expected_value"):
            ev = explainer.expected_value
            expected = float(np.asarray(ev).ravel()[0])
    else:
        explainer = shap.Explainer(estimator.predict, background)
        shap_city = np.asarray(explainer(Xt_city).values)
        shap_local = np.asarray(explainer(Xt_latest).values)
        method, local_method = "city_mean_abs_shap", "local_signed_shap"
        if hasattr(explainer, "expected_value"):
            expected = float(np.asarray(explainer.expected_value).ravel()[0])

    if shap_city.ndim == 3:
        shap_city = shap_city[:, :, 0]
        shap_local = shap_local[:, :, 0]
    return shap_city, shap_local.reshape(-1), expected, method, local_method


def _explain_one_horizon(
    city: str,
    horizon_hours: int,
    config: dict[str, Any],
    pollutants: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    bundle = load_horizon_bundle(horizon_hours, config)
    meta = bundle["meta"]
    feature_cols = meta["feature_cols"]

    if bundle["type"] != "sklearn":
        return {
            "available": False,
            "horizon_hours": horizon_hours,
            "model": meta.get("name"),
            "error": "SHAP currently supports sklearn winners only.",
            "top_features": [],
            "local_features": [],
            "local_signed": [],
            "waterfall": None,
            "narrative": "",
        }

    pipe = bundle["model"]
    preprocess = pipe.named_steps["preprocess"]
    model_step = pipe.named_steps["model"]
    estimator = model_step.estimators_[0] if hasattr(model_step, "estimators_") else model_step

    city_frame, latest_ts = _load_city_slice(city, feature_cols, config)
    latest = city_frame.iloc[[-1]]
    Xt_city = preprocess.transform(city_frame)
    Xt_latest = preprocess.transform(latest)
    if hasattr(Xt_city, "toarray"):
        Xt_city = Xt_city.toarray()
        Xt_latest = Xt_latest.toarray()
    Xt_city = np.asarray(Xt_city, dtype=float)
    Xt_latest = np.asarray(Xt_latest, dtype=float)

    try:
        feature_names = list(preprocess.get_feature_names_out())
    except Exception:
        feature_names = [f"f{i}" for i in range(Xt_city.shape[1])]

    prediction = float(estimator.predict(Xt_latest).reshape(-1)[0])

    try:
        shap_city, shap_local, base_value, method, local_method = _shap_for_estimator(
            estimator, Xt_city, Xt_latest, feature_names
        )
        top_features = _ranking_abs(feature_names, np.abs(shap_city).mean(axis=0))
        local_signed = _ranking_signed(feature_names, shap_local)
        local_features = [
            {"feature": x["feature"], "importance": x["importance"], "glossary": x["glossary"]}
            for x in local_signed
        ]
        waterfall = _waterfall(local_signed, base_value, prediction)
        narrative = _narrative(city, horizon_hours, local_signed, prediction)
        note = (
            f"City bars = mean |SHAP| for recent {city} rows. "
            f"Local bars = signed SHAP for the latest hour (+ raises AQI, - lowers AQI)."
        )
    except Exception:
        if hasattr(estimator, "coef_"):
            coefs = np.asarray(estimator.coef_, dtype=float).ravel()
            local_vals = coefs * Xt_latest.ravel()[: len(coefs)]
            top_features = _ranking_abs(feature_names, np.abs(coefs))
            local_signed = _ranking_signed(feature_names, local_vals)
            local_features = [
                {"feature": x["feature"], "importance": x["importance"], "glossary": x["glossary"]}
                for x in local_signed
            ]
            base_value = float(getattr(estimator, "intercept_", 0.0))
            if isinstance(base_value, (list, np.ndarray)):
                base_value = float(np.asarray(base_value).ravel()[0])
            waterfall = _waterfall(local_signed, base_value, prediction)
            narrative = _narrative(city, horizon_hours, local_signed, prediction)
            method, local_method = "city_global_coefficients", "local_coef_x_value"
            note = "Fallback coefficient explanation (signed local contributions)."
        elif hasattr(estimator, "feature_importances_"):
            ranking = _ranking_abs(feature_names, np.asarray(estimator.feature_importances_, dtype=float))
            top_features = ranking
            local_signed = ranking
            local_features = ranking
            waterfall = None
            narrative = _narrative(city, horizon_hours, local_signed, prediction)
            method, local_method = "city_tree_importances", "tree_importances"
            note = "Fallback tree importances (unsigned)."
        else:
            return {
                "available": False,
                "horizon_hours": horizon_hours,
                "model": meta.get("name"),
                "error": "Could not compute explanation.",
                "top_features": [],
                "local_features": [],
                "local_signed": [],
                "waterfall": None,
                "narrative": "",
            }

    return {
        "available": True,
        "horizon_hours": horizon_hours,
        "model": meta.get("name"),
        "method": method,
        "local_method": local_method,
        "sample_rows": int(len(city_frame)),
        "event_time": latest_ts,
        "prediction": round(prediction, 1),
        "top_features": top_features,
        "local_features": local_features,
        "local_signed": local_signed,
        "waterfall": waterfall,
        "narrative": narrative,
        "pollutant_link": _pollutant_link(local_signed, pollutants),
        "note": note,
    }


def global_shap_summary(config: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = config or load_config()
    path = get_project_root() / cfg["storage"]["shap_path"]
    if not path.exists():
        return {"available": False, "note": "No training-time SHAP summary found.", "top_features": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    top = _annotate_features(
        [
            {
                "feature": x.get("feature"),
                "contribution": float(x.get("importance", 0)),
                "importance": float(x.get("importance", 0)),
            }
            for x in (data.get("top_features") or [])[:12]
        ]
    )
    return {
        "available": bool(data.get("available")),
        "method": data.get("method"),
        "top_features": top,
        "note": "Global drivers from the latest training run (not city-specific).",
    }


def explain_city_compare(config: dict[str, Any] | None = None, horizon_hours: int = 24) -> dict[str, Any]:
    import time

    cfg = config or load_config()
    cache_key = f"compare:{horizon_hours}"
    now = time.monotonic()
    cached = _COMPARE_CACHE.get(cache_key)
    if cached and now - cached[0] < _COMPARE_TTL_SEC:
        return cached[1]

    cities = [c["name"] for c in cfg.get("cities", [])]
    rows = []
    for name in cities:
        try:
            one = _explain_one_horizon(name, horizon_hours, cfg)
            rows.append(
                {
                    "city": name,
                    "available": one.get("available", False),
                    "top_features": (one.get("top_features") or [])[:5],
                    "narrative": one.get("narrative"),
                    "prediction": one.get("prediction"),
                }
            )
        except Exception as exc:
            rows.append({"city": name, "available": False, "error": str(exc), "top_features": []})
    result = {
        "available": any(r.get("available") for r in rows),
        "horizon_hours": horizon_hours,
        "cities": rows,
        "note": f"Top city-level |SHAP| drivers at +{horizon_hours}h for each Pakistan city.",
    }
    _COMPARE_CACHE[cache_key] = (now, result)
    return result


def explain_city(
    city: str,
    config: dict[str, Any] | None = None,
    horizon_hours: int | None = None,
    include_all_horizons: bool = True,
) -> dict[str, Any]:
    import time
    from concurrent.futures import ThreadPoolExecutor, as_completed

    cfg = config or load_config()
    horizons = [int(h) for h in (cfg.get("horizons_hours") or [24, 48, 72])]
    primary = int(horizon_hours or horizons[0])

    cache_key = f"{city}:{primary}:all={include_all_horizons}"
    now = time.monotonic()
    cached = _EXPLAIN_CACHE.get(cache_key)
    if cached and now - cached[0] < _EXPLAIN_TTL_SEC:
        return cached[1]

    pollutants = None
    try:
        from src.inference.predict import current_weather_for_city

        weather = current_weather_for_city(city, cfg)
        pollutants = weather.get("pollutants")
    except Exception:
        pollutants = None

    targets = horizons if include_all_horizons else [primary]
    horizons_out: dict[str, Any] = {}

    def _run(h: int) -> tuple[int, dict[str, Any]]:
        try:
            return h, _explain_one_horizon(city, h, cfg, pollutants=pollutants)
        except Exception as exc:
            return h, {
                "available": False,
                "horizon_hours": h,
                "error": str(exc),
                "top_features": [],
                "local_features": [],
                "local_signed": [],
                "waterfall": None,
                "narrative": "",
            }

    if len(targets) == 1:
        h, pack = _run(targets[0])
        horizons_out[str(h)] = pack
    else:
        with ThreadPoolExecutor(max_workers=min(3, len(targets))) as pool:
            futures = [pool.submit(_run, h) for h in targets]
            for fut in as_completed(futures):
                h, pack = fut.result()
                horizons_out[str(h)] = pack

    primary_pack = horizons_out.get(str(primary)) or next(iter(horizons_out.values()), {})

    result = {
        "available": bool(primary_pack.get("available")),
        "city": city,
        "model": primary_pack.get("model"),
        "horizon": f"aqi_target_{primary}h",
        "horizon_hours": primary,
        "scope": "city",
        "method": primary_pack.get("method"),
        "local_method": primary_pack.get("local_method"),
        "sample_rows": primary_pack.get("sample_rows"),
        "event_time": primary_pack.get("event_time"),
        "prediction": primary_pack.get("prediction"),
        "top_features": primary_pack.get("top_features") or [],
        "local_features": primary_pack.get("local_features") or [],
        "local_signed": primary_pack.get("local_signed") or [],
        "waterfall": primary_pack.get("waterfall"),
        "narrative": primary_pack.get("narrative") or "",
        "pollutant_link": primary_pack.get("pollutant_link"),
        "note": primary_pack.get("note"),
        "horizons": horizons_out,
        "horizons_hours": horizons,
        "global_summary": global_shap_summary(cfg),
        "glossary": {k: FEATURE_GLOSSARY[k] for k in list(FEATURE_GLOSSARY)[:24]},
    }
    _EXPLAIN_CACHE[cache_key] = (now, result)
    return result
