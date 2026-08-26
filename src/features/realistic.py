from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

def _horizon_from_fwd_col(col: str) -> int | None:
    if "_fwd_" not in col:
        return None
    part = col.rsplit("_fwd_", 1)[-1]
    if not part.endswith("h"):
        return None
    try:
        return int(part[:-1])
    except ValueError:
        return None

def forecast_noise_scales(config: dict[str, Any] | None = None) -> dict[int, float]:
    cfg = (config or {}).get("forecast_weather_noise") or {}
    return {
        24: float(cfg.get("scale_24h", 0.08)),
        48: float(cfg.get("scale_48h", 0.12)),
        72: float(cfg.get("scale_72h", 0.16)),
    }

def apply_forecast_weather_noise(
    frame: pd.DataFrame,
    feature_cols: list[str],
    *,
    config: dict[str, Any] | None = None,
    seed: int = 42,
    noise_enabled: bool | None = None,
) -> pd.DataFrame:
    cfg = config or {}
    noise_cfg = cfg.get("forecast_weather_noise") or {}
    enabled = noise_cfg.get("enabled", True) if noise_enabled is None else noise_enabled
    if not enabled:
        return frame

    scales = forecast_noise_scales(cfg)
    out = frame.copy()
    rng = np.random.default_rng(seed)

    for col in feature_cols:
        if col not in out.columns:
            continue
        horizon = _horizon_from_fwd_col(col)
        if horizon is None:
            continue
        scale = scales.get(horizon, 0.1)
        values = pd.to_numeric(out[col], errors="coerce").to_numpy(dtype=float)
        noise = rng.normal(0.0, scale, size=len(values))
        if "wind_direction" in col:
            noisy = values + rng.normal(0.0, 25.0 * (scale / 0.1), size=len(values))
            noisy = np.mod(noisy, 360.0)
        else:
            noisy = values * (1.0 + noise)
            if "precipitation" in col:
                noisy = np.clip(noisy, 0.0, None)
            if "relative_humidity" in col:
                noisy = np.clip(noisy, 0.0, 100.0)
            if "cloud_cover" in col:
                noisy = np.clip(noisy, 0.0, 100.0)
        out[col] = noisy
    return out

def residual_prediction_interval(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    level: float = 0.8,
) -> dict[str, float]:
    yt = np.asarray(y_true, dtype=float).ravel()
    yp = np.asarray(y_pred, dtype=float).ravel()
    mask = np.isfinite(yt) & np.isfinite(yp)
    residuals = yt[mask] - yp[mask]
    if len(residuals) == 0:
        return {
            "level": float(level),
            "residual_std": float("nan"),
            "q_low": float("nan"),
            "q_high": float("nan"),
        }
    alpha = (1.0 - level) / 2.0
    return {
        "level": float(level),
        "residual_std": float(np.std(residuals)),
        "q_low": float(np.quantile(residuals, alpha)),
        "q_high": float(np.quantile(residuals, 1.0 - alpha)),
    }

def apply_interval(pred: float, interval: dict[str, Any] | None) -> tuple[float, float]:
    if not interval or not np.isfinite(interval.get("q_low", np.nan)):
        return float(pred), float(pred)
    low = max(0.0, float(pred) + float(interval["q_low"]))
    high = max(low, float(pred) + float(interval["q_high"]))
    return low, high
