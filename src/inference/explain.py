from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.inference.predict import load_horizon_bundle
from src.utils.config import load_config
from src.utils.storage import load_features
from src.utils.timezone import latest_observed_row

def _load_city_slice(
    city: str,
    feature_cols: list[str],
    config: dict[str, Any],
    max_rows: int = 120,
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

def _ranking_from_values(names: list[str], values: np.ndarray, top_k: int = 12) -> list[dict[str, float | str]]:
    values = np.asarray(values, dtype=float).ravel()
    pairs = [{"feature": str(n), "importance": float(abs(v))} for n, v in zip(names, values)]
    return sorted(pairs, key=lambda x: x["importance"], reverse=True)[:top_k]

def _local_linear_contributions(
    estimator,
    x_row: np.ndarray,
    feature_names: list[str],
) -> list[dict[str, float | str]]:
    coefs = np.asarray(estimator.coef_, dtype=float).ravel()
    contrib = coefs * x_row.ravel()
    return _ranking_from_values(feature_names, contrib)

def explain_city(city: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = config or load_config()
    bundle = load_horizon_bundle(24, cfg)
    meta = bundle["meta"]
    feature_cols = meta["feature_cols"]

    if bundle["type"] != "sklearn":
        return {
            "available": False,
            "city": city,
            "model": meta.get("name"),
            "scope": "city",
            "error": "Per-city SHAP currently supports sklearn winners only.",
            "top_features": [],
            "local_features": [],
        }

    pipe = bundle["model"]
    preprocess = pipe.named_steps["preprocess"]
    model_step = pipe.named_steps["model"]
    estimator = model_step.estimators_[0] if hasattr(model_step, "estimators_") else model_step

    city_frame, latest_ts = _load_city_slice(city, feature_cols, cfg)
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

    try:
        import shap

        background_n = min(40, len(Xt_city))
        background = shap.sample(Xt_city, background_n) if len(Xt_city) > background_n else Xt_city

        if hasattr(estimator, "coef_"):
            explainer = shap.LinearExplainer(estimator, background)
            shap_city = explainer.shap_values(Xt_city)
            shap_local = explainer.shap_values(Xt_latest)
            method = "city_mean_abs_shap"
            local_method = "local_shap"
        elif hasattr(estimator, "feature_importances_"):
            explainer = shap.TreeExplainer(estimator)
            shap_city = explainer.shap_values(Xt_city)
            shap_local = explainer.shap_values(Xt_latest)
            method = "city_mean_abs_shap"
            local_method = "local_shap"
        else:
            explainer = shap.Explainer(estimator.predict, background)
            shap_city = explainer(Xt_city).values
            shap_local = explainer(Xt_latest).values
            method = "city_mean_abs_shap"
            local_method = "local_shap"

        shap_city = np.asarray(shap_city)
        shap_local = np.asarray(shap_local)
        if shap_city.ndim == 3:
            shap_city = shap_city[:, :, 0]
            shap_local = shap_local[:, :, 0]

        return {
            "available": True,
            "city": city,
            "model": meta.get("name"),
            "horizon": "aqi_target_24h",
            "scope": "city",
            "method": method,
            "local_method": local_method,
            "sample_rows": int(len(city_frame)),
            "event_time": latest_ts,
            "top_features": _ranking_from_values(feature_names, np.abs(shap_city).mean(axis=0)),
            "local_features": _ranking_from_values(feature_names, shap_local.reshape(-1)),
            "note": (
                f"City-level bars = mean |SHAP| over recent {city} rows. "
                f"Local bars = SHAP for the latest {city} forecast hour."
            ),
        }
    except Exception:
        if hasattr(estimator, "coef_"):
            return {
                "available": True,
                "city": city,
                "model": meta.get("name"),
                "horizon": "aqi_target_24h",
                "scope": "city",
                "method": "city_global_coefficients",
                "local_method": "local_coef_x_value",
                "sample_rows": int(len(city_frame)),
                "event_time": latest_ts,
                "top_features": _ranking_from_values(
                    feature_names, np.abs(np.asarray(estimator.coef_, dtype=float).ravel())
                ),
                "local_features": _local_linear_contributions(estimator, Xt_latest, feature_names),
                "note": (
                    f"City-level ranking for {city} using model coefficients; "
                    "local bars show coef * feature value for the latest hour."
                ),
            }
        if hasattr(estimator, "feature_importances_"):
            ranking = _ranking_from_values(feature_names, np.asarray(estimator.feature_importances_, dtype=float))
            return {
                "available": True,
                "city": city,
                "model": meta.get("name"),
                "horizon": "aqi_target_24h",
                "scope": "city",
                "method": "city_tree_importances",
                "local_method": "tree_importances",
                "sample_rows": int(len(city_frame)),
                "event_time": latest_ts,
                "top_features": ranking,
                "local_features": ranking,
                "note": f"Fallback tree importances shown for {city}.",
            }
        return {
            "available": False,
            "city": city,
            "model": meta.get("name"),
            "scope": "city",
            "top_features": [],
            "local_features": [],
            "error": "Could not compute city-specific explanation.",
        }
