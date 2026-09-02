from __future__ import annotations

import copy
import json
import threading
import time
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from src.data.openmeteo import fetch_weather_forecast
from src.features.engineering import FUTURE_WEATHER_COLS
from src.features.realistic import apply_interval
from src.utils.aqi_bands import aqi_category, aqi_color, is_hazardous_alert
from src.utils.config import get_project_root, load_config
from src.utils.storage import load_features
from src.utils.timezone import latest_observed_row

_WINNER_MEM: dict[str, Any] = {}
_PREDICT_MEM: dict[str, tuple[float, dict[str, Any]]] = {}
_PREDICT_LOCKS: dict[str, threading.Lock] = {}
_WEATHER_MEM: dict[str, tuple[float, pd.DataFrame]] = {}
PREDICT_TTL_SEC = 120.0
WEATHER_TTL_SEC = 600.0

def _model_dir(config: dict[str, Any] | None = None) -> Path:
    cfg = config or load_config()
    return get_project_root() / cfg["storage"]["model_dir"]

def _city_meta(city: str, config: dict[str, Any]) -> dict[str, Any] | None:
    for item in config.get("cities", []):
        if item.get("name") == city:
            return item
    return None

def _weather_forecast_cached(lat: float, lon: float) -> pd.DataFrame:
    key = f"{lat:.4f},{lon:.4f}"
    now = time.monotonic()
    cached = _WEATHER_MEM.get(key)
    if cached and now - cached[0] < WEATHER_TTL_SEC:
        return cached[1]

    forecast = fetch_weather_forecast(lat, lon, forecast_days=4)
    _WEATHER_MEM[key] = (now, forecast)
    return forecast

def _fill_future_weather_row(
    row: pd.Series,
    city: str,
    config: dict[str, Any],
    feature_cols: list[str],
    event_time: pd.Timestamp,
    weather_forecast: pd.DataFrame | None = None,
) -> pd.Series:
    needed = [c for c in feature_cols if "_fwd_" in c and (pd.isna(row.get(c)) if c in row.index else True)]
    if not needed:
        needed = [c for c in feature_cols if "_fwd_" in c]
    if not needed:
        return row

    meta = _city_meta(city, config)
    if not meta:
        return row

    try:
        forecast = weather_forecast
        if forecast is None:
            forecast = _weather_forecast_cached(meta["lat"], meta["lon"])
    except Exception as exc:
        print(f"[predict] weather forecast fetch failed for {city}: {exc}")
        return row

    if forecast.empty:
        return row

    forecast = forecast.set_index(pd.to_datetime(forecast["event_time"], utc=True))
    out = row.copy()
    base_time = pd.to_datetime(event_time, utc=True)

    for col in needed:
        if "_fwd_" not in col:
            continue
        base, _, horizon_part = col.rpartition("_fwd_")
        try:
            hours = int(horizon_part.replace("h", ""))
        except ValueError:
            continue
        if base not in FUTURE_WEATHER_COLS:
            continue
        target_ts = base_time + pd.Timedelta(hours=hours)
        if base not in forecast.columns or forecast.empty:
            continue
        if target_ts in forecast.index:
            val = forecast.loc[target_ts, base]
            out[col] = float(val.iloc[0] if isinstance(val, pd.Series) else val)
            continue
        deltas = np.abs((forecast.index - target_ts).total_seconds())
        nearest_i = int(np.argmin(deltas))
        if deltas[nearest_i] <= 90 * 60:
            nearest_ts = forecast.index[nearest_i]
            val = forecast.loc[nearest_ts, base]
            out[col] = float(val.iloc[0] if isinstance(val, pd.Series) else val)
    return out

def load_winner(config: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = config or load_config()
    model_dir = _model_dir(cfg)
    winner_path = model_dir / "winner.json"
    if not winner_path.exists():
        raise FileNotFoundError("No trained winner found. Run training_pipeline.py first.")

    mtime = winner_path.stat().st_mtime
    if _WINNER_MEM.get("mtime") == mtime and _WINNER_MEM.get("bundle") is not None:
        return _WINNER_MEM["bundle"]

    meta = json.loads(winner_path.read_text(encoding="utf-8"))
    if meta.get("mode") == "per_horizon" or meta.get("type") == "per_horizon":
        horizons = meta.get("horizons_hours") or cfg["horizons_hours"]
        models: dict[int, Any] = {}
        for h in horizons:
            h_meta = meta["horizon_winners"][str(h)]
            if h_meta["type"] == "sklearn":
                models[int(h)] = {
                    "type": "sklearn",
                    "model": joblib.load(model_dir / f"winner_{h}h.joblib"),
                    "meta": h_meta,
                }
            else:
                from tensorflow import keras

                lstm_meta = json.loads(
                    (model_dir / f"winner_{h}h_lstm_meta.json").read_text(encoding="utf-8")
                )
                models[int(h)] = {
                    "type": "keras",
                    "model": keras.models.load_model(model_dir / f"winner_{h}h.keras"),
                    "meta": h_meta,
                    "lstm_meta": lstm_meta,
                }
        bundle = {"meta": meta, "type": "per_horizon", "models": models}
        _WINNER_MEM["mtime"] = mtime
        _WINNER_MEM["bundle"] = bundle
        return bundle

    if meta["type"] == "sklearn":
        model = joblib.load(model_dir / "winner.joblib")
        bundle = {"meta": meta, "model": model, "type": "sklearn"}
        _WINNER_MEM["mtime"] = mtime
        _WINNER_MEM["bundle"] = bundle
        return bundle

    from tensorflow import keras

    model = keras.models.load_model(model_dir / "winner.keras")
    lstm_meta = json.loads((model_dir / "winner_lstm_meta.json").read_text(encoding="utf-8"))
    bundle = {"meta": meta, "model": model, "type": "keras", "lstm_meta": lstm_meta}
    _WINNER_MEM["mtime"] = mtime
    _WINNER_MEM["bundle"] = bundle
    return bundle

def load_horizon_bundle(horizon_hours: int = 24, config: dict[str, Any] | None = None) -> dict[str, Any]:
    bundle = load_winner(config)
    if bundle["type"] != "per_horizon":
        return bundle
    models = bundle["models"]
    if horizon_hours not in models:
        horizon_hours = sorted(models.keys())[0]
    item = models[horizon_hours]
    return {
        "meta": {**bundle["meta"], **item["meta"], "name": item["meta"]["name"]},
        "model": item["model"],
        "type": item["type"],
        "lstm_meta": item.get("lstm_meta"),
        "horizon_hours": horizon_hours,
    }

def _flatten_scaler(arr, n_features: int) -> np.ndarray:
    values = np.asarray(arr, dtype=np.float32).reshape(-1)
    if values.size == n_features:
        return values
    return values.reshape(-1, n_features)[0]

def _predict_sklearn_row(model, row: pd.Series, feature_cols: list[str]) -> float:
    X = pd.DataFrame([{ "city": row["city"], **{c: row.get(c) for c in feature_cols} }])
    for c in feature_cols:
        X[c] = pd.to_numeric(X[c], errors="coerce")
    X[feature_cols] = X[feature_cols].fillna(0)
    pred = model.predict(X[["city", *feature_cols]])
    value = float(np.asarray(pred).reshape(-1)[0])
    return value

def _predict_keras_city(
    model,
    lstm_meta: dict[str, Any],
    city_df: pd.DataFrame,
) -> float:
    seq_len = int(lstm_meta["seq_len"])
    cols = lstm_meta["feature_cols"]
    if len(city_df) < seq_len:
        raise RuntimeError(f"Need at least {seq_len} rows for LSTM inference")
    work = city_df.copy()
    for c in cols:
        if c not in work.columns:
            work[c] = 0.0
    seq = work.iloc[-seq_len:][cols].astype(float).fillna(0).values.astype(np.float32)
    mean_arr = _flatten_scaler(lstm_meta["scaler_mean"], len(cols))
    std_arr = _flatten_scaler(lstm_meta["scaler_std"], len(cols))
    seq = (seq - mean_arr) / (std_arr + 1e-6)
    pred = model.predict(seq[None, ...], verbose=0)[0]
    return float(np.asarray(pred).reshape(-1)[0])

def predict_city(city: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
    key = city.strip().lower()
    lock = _PREDICT_LOCKS.setdefault(key, threading.Lock())

    with lock:
        now = time.monotonic()
        cached = _PREDICT_MEM.get(key)
        if cached and now - cached[0] < PREDICT_TTL_SEC:
            return copy.deepcopy(cached[1])

        result = _predict_city_uncached(city, config)
        _PREDICT_MEM[key] = (now, copy.deepcopy(result))
        return result

def _predict_city_uncached(city: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = config or load_config()
    bundle = load_winner(cfg)
    meta = bundle["meta"]
    horizons = cfg["horizons_hours"]

    df = load_features(cfg)
    city_df = df[df["city"] == city].sort_values("event_time").copy()
    if city_df.empty:
        raise ValueError(f"No data for city={city}")

    current = latest_observed_row(city_df).copy()
    current_aqi = float(current["aqi"]) if pd.notna(current.get("aqi")) else None
    event_time = pd.to_datetime(current["event_time"], utc=True)

    weather_forecast: pd.DataFrame | None = None
    city_meta = _city_meta(city, cfg)
    if city_meta:
        try:
            weather_forecast = _weather_forecast_cached(city_meta["lat"], city_meta["lon"])
        except Exception:
            weather_forecast = None

    forecasts = []
    model_names: list[str] = []

    if bundle["type"] == "per_horizon":
        for h in horizons:
            item = bundle["models"][int(h)]
            h_meta = item["meta"]
            feature_cols = h_meta["feature_cols"]
            model_names.append(f"{h_meta['name']}@{h}h")

            filled = _fill_future_weather_row(
                current, city, cfg, feature_cols, event_time, weather_forecast=weather_forecast
            )
            row_df = city_df.copy()
            for c in feature_cols:
                if c in filled.index:
                    row_df.loc[row_df.index[-1], c] = filled[c]

            if item["type"] == "sklearn":
                value = _predict_sklearn_row(item["model"], filled, feature_cols)
            else:
                value = _predict_keras_city(item["model"], item["lstm_meta"], row_df)

            aqi_val = float(max(0, value))
            low, high = apply_interval(aqi_val, h_meta.get("prediction_interval"))
            interval_level = (h_meta.get("prediction_interval") or {}).get("level", 0.8)
            forecasts.append(
                {
                    "horizon_hours": h,
                    "target": f"aqi_target_{h}h",
                    "aqi": round(aqi_val, 1),
                    "aqi_low": round(low, 1),
                    "aqi_high": round(high, 1),
                    "interval_level": interval_level,
                    "category": aqi_category(aqi_val),
                    "color": aqi_color(aqi_val),
                    "model": h_meta["name"],
                }
            )
        model_label = "+".join(model_names)
    else:
        feature_cols = meta["feature_cols"]
        targets = meta["targets"]
        filled = _fill_future_weather_row(
            current, city, cfg, feature_cols, event_time, weather_forecast=weather_forecast
        )

        if bundle["type"] == "sklearn":
            X = pd.DataFrame([{ "city": city, **{c: filled.get(c) for c in feature_cols} }])
            for c in feature_cols:
                X[c] = pd.to_numeric(X[c], errors="coerce")
            X[feature_cols] = X[feature_cols].fillna(0)
            pred = bundle["model"].predict(X[["city", *feature_cols]])[0]
            pred = np.asarray(pred).reshape(-1)
        else:
            lstm_meta = bundle["lstm_meta"]
            row_df = city_df.copy()
            for c in feature_cols:
                if c in filled.index:
                    row_df.loc[row_df.index[-1], c] = filled[c]
            seq_len = int(lstm_meta["seq_len"])
            cols = lstm_meta["feature_cols"]
            seq = row_df.iloc[-seq_len:][cols].astype(float).fillna(0).values.astype(np.float32)
            mean_arr = _flatten_scaler(lstm_meta["scaler_mean"], len(cols))
            std_arr = _flatten_scaler(lstm_meta["scaler_std"], len(cols))
            seq = (seq - mean_arr) / (std_arr + 1e-6)
            pred = bundle["model"].predict(seq[None, ...], verbose=0)[0]

        for horizon, target, value in zip(horizons, targets, pred):
            aqi_val = float(max(0, value))
            forecasts.append(
                {
                    "horizon_hours": horizon,
                    "target": target,
                    "aqi": round(aqi_val, 1),
                    "category": aqi_category(aqi_val),
                    "color": aqi_color(aqi_val),
                }
            )
        model_label = meta["name"]

    return {
        "city": city,
        "model": model_label,
        "event_time": pd.to_datetime(current["event_time"], utc=True).isoformat(),
        "current_aqi": round(current_aqi, 1) if current_aqi is not None else None,
        "current_category": aqi_category(current_aqi),
        "current_color": aqi_color(current_aqi),
        "forecast": forecasts,
    }

def history_for_city(city: str, hours: int = 168, config: dict[str, Any] | None = None) -> list[dict]:
    df = load_features(config)
    city_df = df[df["city"] == city].sort_values("event_time")
    times = pd.to_datetime(city_df["event_time"], utc=True)
    now = pd.Timestamp.now(tz="UTC").floor("h")
    city_df = city_df[times <= now].tail(hours)
    rows = []
    for _, row in city_df.iterrows():
        aqi = float(row["aqi"]) if pd.notna(row.get("aqi")) else None
        rows.append(
            {
                "event_time": str(row["event_time"]),
                "aqi": None if aqi is None else round(aqi, 1),
                "category": aqi_category(aqi),
                "pm25": None if pd.isna(row.get("pm25")) else float(row["pm25"]),
            }
        )
    return rows

def alerts_for_city(city: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
    prediction = predict_city(city, config)
    alerts = []
    if is_hazardous_alert(prediction["current_aqi"]):
        alerts.append(
            {
                "when": "current",
                "aqi": prediction["current_aqi"],
                "category": prediction["current_category"],
                "message": f"Current AQI in {city} is {prediction['current_category']}.",
            }
        )
    for item in prediction["forecast"]:
        if is_hazardous_alert(item["aqi"]):
            alerts.append(
                {
                    "when": f"+{item['horizon_hours']}h",
                    "aqi": item["aqi"],
                    "category": item["category"],
                    "message": (
                        f"Forecast AQI in {city} reaches {item['category']} "
                        f"in {item['horizon_hours']} hours."
                    ),
                }
            )
    return {"city": city, "alerts": alerts, "has_alerts": bool(alerts)}

def current_weather_for_city(city: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = config or load_config()
    df = load_features(cfg)
    city_df = df[df["city"] == city].sort_values("event_time")
    if city_df.empty:
        raise ValueError(f"No data for city={city}")

    row = latest_observed_row(city_df)
    temperature = None if pd.isna(row.get("temperature_2m")) else float(row["temperature_2m"])
    humidity = None if pd.isna(row.get("relative_humidity_2m")) else float(row["relative_humidity_2m"])
    wind_speed = None if pd.isna(row.get("wind_speed_10m")) else float(row["wind_speed_10m"])
    wind_direction = None if pd.isna(row.get("wind_direction_10m")) else float(row["wind_direction_10m"])
    cloud_cover = None if pd.isna(row.get("cloud_cover")) else float(row["cloud_cover"])
    precipitation = None if pd.isna(row.get("precipitation")) else float(row["precipitation"])
    pressure = None if pd.isna(row.get("surface_pressure")) else float(row["surface_pressure"])

    if wind_speed is not None and wind_speed >= 18:
        driver = "Wind is helping disperse pollution around the city."
    elif humidity is not None and humidity >= 75 and (wind_speed is None or wind_speed < 12):
        driver = "Humid, calmer air may allow pollution to linger for longer."
    elif cloud_cover is not None and cloud_cover >= 70:
        driver = "Cloudier conditions are present, with weaker vertical mixing likely."
    else:
        driver = "Weather is fairly neutral right now, so AQI is driven more by local emissions."

    comfort = "sticky" if humidity is not None and humidity >= 70 else "comfortable"
    breeze = (
        "breezy"
        if wind_speed is not None and wind_speed >= 18
        else "light wind"
        if wind_speed is not None and wind_speed >= 8
        else "still air"
    )

    pm25 = None if pd.isna(row.get("pm25")) else float(row["pm25"])
    pm10 = None if pd.isna(row.get("pm10")) else float(row["pm10"])
    o3 = None if pd.isna(row.get("o3")) else float(row["o3"])
    no2 = None if pd.isna(row.get("no2")) else float(row["no2"])
    so2 = None if pd.isna(row.get("so2")) else float(row["so2"])
    co = None if pd.isna(row.get("co")) else float(row["co"])

    pollutant_meta: list[tuple[str, str, float | None, str, float]] = [
        ("pm25", "PM2.5", pm25, "µg/m³", 55.0),
        ("pm10", "PM10", pm10, "µg/m³", 155.0),
        ("o3", "O₃", o3, "µg/m³", 180.0),
        ("no2", "NO₂", no2, "µg/m³", 100.0),
        ("so2", "SO₂", so2, "µg/m³", 200.0),
        ("co", "CO", co, "µg/m³", 10000.0),
    ]

    pollutants: list[dict[str, Any]] = []
    for key, label, value, unit, ref in pollutant_meta:
        if value is None:
            continue
        intensity = max(0.0, min(100.0, (float(value) / ref) * 100.0))
        if intensity < 30:
            level, color = "Good", "#00e400"
        elif intensity < 55:
            level, color = "Moderate", "#ffff00"
        elif intensity < 75:
            level, color = "Sensitive", "#ff7e00"
        elif intensity < 90:
            level, color = "Unhealthy", "#ff0000"
        else:
            level, color = "Very Unhealthy", "#8f3f97"
        pollutants.append(
            {
                "key": key,
                "label": label,
                "value": round(float(value), 1),
                "unit": unit,
                "intensity_pct": round(intensity, 1),
                "level": level,
                "color": color,
                "is_dominant": False,
            }
        )

    pollutants.sort(key=lambda p: p["intensity_pct"], reverse=True)
    if pollutants:
        pollutants[0]["is_dominant"] = True

    top = (pollutants[0]["key"], pollutants[0]["label"], pollutants[0]["value"]) if pollutants else None
    top2 = [(p["key"], p["label"], p["value"]) for p in pollutants[:3]]

    if not top:
        pollutant_driver = None
        pollutant_driver_detail = "We couldn't read pollutant breakdown right now; AQI is still shown from your live forecast."
    else:
        pollutant_driver = top[1]
        top_value = float(top[2])
        if top[0] == "pm25":
            pollutant_driver_detail = (
                f"{pollutant_driver} is currently the strongest pollutant signal (about {round(top_value, 1)}). "
                "Fine particles typically dominate AQI when air is stagnant."
            )
        elif top[0] == "pm10":
            pollutant_driver_detail = (
                f"{pollutant_driver} is currently the strongest pollutant signal (about {round(top_value, 1)}). "
                "Coarse dust/particulates often spike AQI during high-traffic or windy conditions."
            )
        elif top[0] == "o3":
            pollutant_driver_detail = (
                f"{pollutant_driver} is currently elevated (about {round(top_value, 1)}). "
                "Ozone often rises with sunlight and can make afternoons feel worse even when PM is lower."
            )
        elif top[0] == "no2":
            pollutant_driver_detail = (
                f"{pollutant_driver} is currently elevated (about {round(top_value, 1)}). "
                "Traffic-related emissions can push AQI, especially near busy corridors."
            )
        elif top[0] == "so2":
            pollutant_driver_detail = (
                f"{pollutant_driver} is currently elevated (about {round(top_value, 1)}). "
                "Sulfur dioxide can be associated with industrial activity and fuel combustion spikes."
            )
        else:
            pollutant_driver_detail = (
                f"{pollutant_driver} is currently elevated (about {round(top_value, 1)}). "
                "Carbon monoxide typically tracks combustion sources and ventilation patterns."
            )

    return {
        "city": city,
        "event_time": pd.to_datetime(row["event_time"], utc=True).isoformat(),
        "temperature_c": None if temperature is None else round(temperature, 1),
        "humidity_pct": None if humidity is None else round(humidity),
        "wind_kph": None if wind_speed is None else round(wind_speed, 1),
        "wind_direction_deg": None if wind_direction is None else round(wind_direction),
        "cloud_cover_pct": None if cloud_cover is None else round(cloud_cover),
        "precipitation_mm": None if precipitation is None else round(precipitation, 1),
        "pressure_hpa": None if pressure is None else round(pressure, 1),
        "comfort_label": comfort,
        "air_driver": driver,
        "wind_label": breeze,
        "pollutant_driver": pollutant_driver,
        "pollutant_driver_detail": pollutant_driver_detail,
        "pollutants": pollutants,
        "pollutants_top": [
            {"key": k, "label": label, "value": round(float(v), 2)}
            for (k, label, v) in top2
        ],
    }
