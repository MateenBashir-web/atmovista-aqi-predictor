from __future__ import annotations

import numpy as np
import pandas as pd

RAW_FEATURE_COLS = [
    "pm10",
    "pm25",
    "co",
    "no2",
    "so2",
    "o3",
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
    "wind_speed_10m",
    "wind_direction_10m",
    "cloud_cover",
    "surface_pressure",
    "aqi",
]

FUTURE_WEATHER_COLS = [
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
    "wind_speed_10m",
    "wind_direction_10m",
    "cloud_cover",
    "surface_pressure",
]

def _add_time_features(df: pd.DataFrame) -> pd.DataFrame:
    ts = pd.to_datetime(df["event_time"], utc=True)
    df = df.copy()
    df["hour"] = ts.dt.hour
    df["day"] = ts.dt.day
    df["day_of_week"] = ts.dt.dayofweek
    df["month"] = ts.dt.month
    df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24)
    df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24)
    df["month_sin"] = np.sin(2 * np.pi * df["month"] / 12)
    df["month_cos"] = np.cos(2 * np.pi * df["month"] / 12)
    df["dow_sin"] = np.sin(2 * np.pi * df["day_of_week"] / 7)
    df["dow_cos"] = np.cos(2 * np.pi * df["day_of_week"] / 7)
    return df

def _add_derived_features(
    city_df: pd.DataFrame,
    lag_hours: list[int],
    rolling_windows: list[int],
) -> pd.DataFrame:
    df = city_df.sort_values("event_time").copy()
    df["aqi"] = pd.to_numeric(df["aqi"], errors="coerce")
    df["aqi_change_rate"] = df["aqi"].diff()
    df["aqi_pct_change"] = df["aqi"].pct_change().replace([np.inf, -np.inf], np.nan)

    for lag in lag_hours:
        df[f"aqi_lag_{lag}h"] = df["aqi"].shift(lag)
        if "pm25" in df.columns:
            df[f"pm25_lag_{lag}h"] = pd.to_numeric(df["pm25"], errors="coerce").shift(lag)

    for window in rolling_windows:
        df[f"aqi_roll_mean_{window}h"] = df["aqi"].rolling(window, min_periods=1).mean()
        df[f"aqi_roll_std_{window}h"] = df["aqi"].rolling(window, min_periods=1).std()

    if "temperature_2m" in df.columns and "relative_humidity_2m" in df.columns:
        df["temp_humidity"] = (
            pd.to_numeric(df["temperature_2m"], errors="coerce")
            * pd.to_numeric(df["relative_humidity_2m"], errors="coerce")
        )

    if "wind_speed_10m" in df.columns and "pm25" in df.columns:
        df["wind_pm25"] = (
            pd.to_numeric(df["wind_speed_10m"], errors="coerce")
            * pd.to_numeric(df["pm25"], errors="coerce")
        )

    return df

def _add_future_weather_features(df: pd.DataFrame, horizons: list[int]) -> pd.DataFrame:
    out = df.copy()
    for h in horizons:
        for col in FUTURE_WEATHER_COLS:
            if col in out.columns:
                out[f"{col}_fwd_{h}h"] = pd.to_numeric(out[col], errors="coerce").shift(-h)
    return out

def future_weather_feature_names(horizons: list[int] | None = None) -> list[str]:
    horizons = horizons or [24, 48, 72]
    return [f"{col}_fwd_{h}h" for h in horizons for col in FUTURE_WEATHER_COLS]

def _add_targets(df: pd.DataFrame, horizons: list[int]) -> pd.DataFrame:
    out = df.copy()
    for h in horizons:
        out[f"aqi_target_{h}h"] = out["aqi"].shift(-h)
    return out

def engineer_features(
    raw_df: pd.DataFrame,
    horizons_hours: list[int] | None = None,
    lag_hours: list[int] | None = None,
    rolling_windows_hours: list[int] | None = None,
) -> pd.DataFrame:
    if raw_df.empty:
        return raw_df

    horizons = horizons_hours or [24, 48, 72]
    lags = lag_hours or [1, 3, 6, 12, 24, 48, 72]
    rolls = rolling_windows_hours or [6, 12, 24]

    target_cols = {f"aqi_target_{h}h" for h in horizons}
    fwd_cols = set(future_weather_feature_names(horizons))
    no_fill = target_cols | fwd_cols

    frames: list[pd.DataFrame] = []
    for city, group in raw_df.groupby("city", sort=False):
        g = group.copy()
        for col in RAW_FEATURE_COLS:
            if col in g.columns:
                g[col] = pd.to_numeric(g[col], errors="coerce")

        g = _add_time_features(g)
        g = _add_derived_features(g, lags, rolls)
        g = _add_future_weather_features(g, horizons)
        g = _add_targets(g, horizons)

        numeric_cols = [c for c in g.select_dtypes(include=[np.number]).columns if c not in no_fill]
        g[numeric_cols] = g[numeric_cols].ffill().bfill()
        frames.append(g)

    features = pd.concat(frames, ignore_index=True)
    features = features.sort_values(["city", "event_time"]).reset_index(drop=True)
    return features

def raw_like_frame(df: pd.DataFrame) -> pd.DataFrame:
    keep = ["event_time", "city", "country", "lat", "lon", "european_aqi", "us_aqi", *RAW_FEATURE_COLS]
    cols = [c for c in keep if c in df.columns]
    out = df[cols].copy()
    out["event_time"] = pd.to_datetime(out["event_time"], utc=True)
    out = out.drop_duplicates(subset=["city", "event_time"], keep="last")
    return out.sort_values(["city", "event_time"]).reset_index(drop=True)

def feature_columns(
    df: pd.DataFrame,
    horizons_hours: list[int] | None = None,
    horizon_hours: int | None = None,
) -> list[str]:
    horizons = horizons_hours or [24, 48, 72]
    target_cols = {f"aqi_target_{h}h" for h in horizons}
    exclude = {
        "event_time",
        "city",
        "country",
        "lat",
        "lon",
        "european_aqi",
        "us_aqi",
        *target_cols,
    }
    if horizon_hours is not None:
        for h in horizons:
            if h == horizon_hours:
                continue
            for col in FUTURE_WEATHER_COLS:
                exclude.add(f"{col}_fwd_{h}h")

    cols = []
    for c in df.columns:
        if c in exclude:
            continue
        if pd.api.types.is_numeric_dtype(df[c]):
            cols.append(c)
    return cols

def target_columns(horizons_hours: list[int] | None = None) -> list[str]:
    horizons = horizons_hours or [24, 48, 72]
    return [f"aqi_target_{h}h" for h in horizons]
