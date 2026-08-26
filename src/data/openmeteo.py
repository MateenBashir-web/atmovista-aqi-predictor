from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

import time

import pandas as pd
import requests

AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
WEATHER_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

AQ_HOURLY = [
    "pm10",
    "pm2_5",
    "carbon_monoxide",
    "nitrogen_dioxide",
    "sulphur_dioxide",
    "ozone",
    "european_aqi",
    "us_aqi",
]

WEATHER_HOURLY = [
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
    "wind_speed_10m",
    "wind_direction_10m",
    "cloud_cover",
    "surface_pressure",
]

def _get_json(
    url: str,
    params: dict[str, Any],
    timeout: int = 90,
    retries: int = 4,
) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
            last_error = exc
            if attempt >= retries:
                break
            sleep_s = min(2 ** attempt, 20)
            time.sleep(sleep_s)
        except requests.exceptions.HTTPError as exc:
            last_error = exc
            status = getattr(exc.response, "status_code", None)
            if status is None or status < 500 or attempt >= retries:
                raise
            time.sleep(min(2 ** attempt, 20))
    assert last_error is not None
    raise last_error

def _hourly_to_frame(payload: dict[str, Any], prefix: str = "") -> pd.DataFrame:
    hourly = payload.get("hourly") or {}
    if "time" not in hourly:
        return pd.DataFrame()
    df = pd.DataFrame(hourly)
    df = df.rename(columns={"time": "event_time"})
    df["event_time"] = pd.to_datetime(df["event_time"], utc=True)
    if prefix:
        rename = {c: f"{prefix}{c}" for c in df.columns if c != "event_time"}
        df = df.rename(columns=rename)
    return df

def fetch_air_quality(
    lat: float,
    lon: float,
    start: date | None = None,
    end: date | None = None,
) -> pd.DataFrame:
    params: dict[str, Any] = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ",".join(AQ_HOURLY),
        "timezone": "UTC",
    }
    if start and end:
        params["start_date"] = start.isoformat()
        params["end_date"] = end.isoformat()
    else:
        params["past_days"] = 7
        params["forecast_days"] = 1

    payload = _get_json(AIR_QUALITY_URL, params)
    df = _hourly_to_frame(payload)
    if df.empty:
        return df
    rename_map = {
        "pm2_5": "pm25",
        "carbon_monoxide": "co",
        "nitrogen_dioxide": "no2",
        "sulphur_dioxide": "so2",
        "ozone": "o3",
        "european_aqi": "european_aqi",
        "us_aqi": "us_aqi",
    }
    df = df.rename(columns=rename_map)
    return df

def fetch_weather(
    lat: float,
    lon: float,
    start: date | None = None,
    end: date | None = None,
    forecast_days: int = 1,
) -> pd.DataFrame:
    params: dict[str, Any] = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ",".join(WEATHER_HOURLY),
        "timezone": "UTC",
    }

    if start and end:
        today = datetime.now(timezone.utc).date()
        if end < today - timedelta(days=2):
            url = WEATHER_ARCHIVE_URL
            params["start_date"] = start.isoformat()
            params["end_date"] = end.isoformat()
        else:
            url = WEATHER_URL
            params["start_date"] = start.isoformat()
            params["end_date"] = end.isoformat()
    else:
        url = WEATHER_URL
        params["past_days"] = 7
        params["forecast_days"] = max(1, int(forecast_days))

    payload = _get_json(url, params)
    return _hourly_to_frame(payload)

def fetch_weather_forecast(
    lat: float,
    lon: float,
    forecast_days: int = 4,
) -> pd.DataFrame:
    params: dict[str, Any] = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ",".join(WEATHER_HOURLY),
        "timezone": "UTC",
        "forecast_days": max(1, int(forecast_days)),
    }
    payload = _get_json(WEATHER_URL, params)
    return _hourly_to_frame(payload)

def fetch_city_raw(
    city: dict[str, Any],
    start: date | None = None,
    end: date | None = None,
) -> pd.DataFrame:
    aq = fetch_air_quality(city["lat"], city["lon"], start=start, end=end)
    weather = fetch_weather(city["lat"], city["lon"], start=start, end=end)
    if aq.empty and weather.empty:
        return pd.DataFrame()

    if aq.empty:
        merged = weather.copy()
    elif weather.empty:
        merged = aq.copy()
    else:
        merged = pd.merge(aq, weather, on="event_time", how="outer")

    merged["city"] = city["name"]
    merged["country"] = city.get("country", "Pakistan")
    merged["lat"] = city["lat"]
    merged["lon"] = city["lon"]
    merged = merged.sort_values("event_time").reset_index(drop=True)

    if "us_aqi" in merged.columns and "european_aqi" in merged.columns:
        merged["aqi"] = merged["us_aqi"].fillna(merged["european_aqi"])
    elif "us_aqi" in merged.columns:
        merged["aqi"] = merged["us_aqi"]
    elif "european_aqi" in merged.columns:
        merged["aqi"] = merged["european_aqi"]
    else:
        merged["aqi"] = pd.NA

    return merged

def fetch_all_cities_raw(
    cities: list[dict[str, Any]],
    start: date | None = None,
    end: date | None = None,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for city in cities:
        frame = fetch_city_raw(city, start=start, end=end)
        if not frame.empty:
            frames.append(frame)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)
