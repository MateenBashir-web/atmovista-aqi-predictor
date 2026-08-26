from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from src.utils.aqi_bands import aqi_category

def regression_metrics(y_true, y_pred) -> dict[str, float]:
    y_true = np.asarray(y_true, dtype=float).ravel()
    y_pred = np.asarray(y_pred, dtype=float).ravel()
    mask = np.isfinite(y_true) & np.isfinite(y_pred)
    y_true = y_true[mask]
    y_pred = y_pred[mask]
    if len(y_true) == 0:
        return {
            "rmse": float("nan"),
            "mae": float("nan"),
            "r2": float("nan"),
            "category_accuracy": float("nan"),
        }

    mse = mean_squared_error(y_true, y_pred)
    cats_true = [aqi_category(v) for v in y_true]
    cats_pred = [aqi_category(v) for v in y_pred]
    cat_acc = float(np.mean([a == b for a, b in zip(cats_true, cats_pred)]))
    return {
        "rmse": float(np.sqrt(mse)),
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "r2": float(r2_score(y_true, y_pred)),
        "category_accuracy": cat_acc,
    }

def average_horizon_metrics(per_horizon: dict[str, dict[str, float]]) -> dict[str, float]:
    keys = ("rmse", "mae", "r2", "category_accuracy")
    out: dict[str, Any] = {}
    for key in keys:
        vals = [m[key] for m in per_horizon.values() if key in m and np.isfinite(m.get(key, np.nan))]
        out[key] = float(np.mean(vals)) if vals else float("nan")
    return out

def persistence_metrics(y_true, current_aqi) -> dict[str, float]:
    return regression_metrics(y_true, current_aqi)
