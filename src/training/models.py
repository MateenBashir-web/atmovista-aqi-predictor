from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from src.features.engineering import feature_columns, target_columns
from src.features.realistic import apply_forecast_weather_noise, residual_prediction_interval
from src.utils.metrics import average_horizon_metrics, persistence_metrics, regression_metrics

def prepare_supervised(
    df: pd.DataFrame,
    horizons_hours: list[int],
    horizon_hours: int | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, list[str], list[str]]:
    if horizon_hours is not None:
        targets = [f"aqi_target_{horizon_hours}h"]
        feat_cols = feature_columns(df, horizons_hours, horizon_hours=horizon_hours)
    else:
        targets = target_columns(horizons_hours)
        feat_cols = feature_columns(df, horizons_hours)

    work = df.dropna(subset=targets).copy()
    work["event_time"] = pd.to_datetime(work["event_time"], utc=True)
    work = work.sort_values("event_time")

    X = work[["city", "event_time", *feat_cols]].copy()
    y = work[targets].copy()
    return X, y, feat_cols, targets

def time_based_split(
    X: pd.DataFrame,
    y: pd.DataFrame,
    validation_days: int,
    test_days: int,
) -> dict[str, Any]:
    times = pd.to_datetime(X["event_time"], utc=True)
    max_time = times.max()
    min_time = times.min()
    span_days = max((max_time - min_time).total_seconds() / 86400.0, 1.0)

    if span_days < (validation_days + test_days + 7):
        test_start = min_time + pd.Timedelta(days=span_days * 0.7)
        val_start = min_time + pd.Timedelta(days=span_days * 0.55)
    else:
        test_start = max_time - pd.Timedelta(days=test_days)
        val_start = test_start - pd.Timedelta(days=validation_days)

    test_mask = times > test_start
    val_mask = (times > val_start) & (times <= test_start)
    train_mask = times <= val_start

    def _pack(mask):
        return X.loc[mask].reset_index(drop=True), y.loc[mask].reset_index(drop=True)

    X_train, y_train = _pack(train_mask)
    X_val, y_val = _pack(val_mask)
    X_test, y_test = _pack(test_mask)
    return {
        "X_train": X_train,
        "y_train": y_train,
        "X_val": X_val,
        "y_val": y_val,
        "X_test": X_test,
        "y_test": y_test,
        "val_start": val_start,
        "test_start": test_start,
    }

def build_preprocess(feature_cols: list[str]) -> ColumnTransformer:
    return ColumnTransformer(
        transformers=[
            ("city", OneHotEncoder(handle_unknown="ignore"), ["city"]),
            ("num", StandardScaler(), feature_cols),
        ]
    )

def build_sklearn_models(random_seed: int = 42) -> dict[str, Any]:
    return {
        "ridge": Ridge(alpha=1.0),
        "random_forest": RandomForestRegressor(
            n_estimators=120,
            max_depth=12,
            n_jobs=-1,
            random_state=random_seed,
        ),
        "hist_gradient_boosting": HistGradientBoostingRegressor(
            max_depth=8,
            learning_rate=0.08,
            random_state=random_seed,
        ),
    }

def evaluate_predictions(
    y_true: pd.Series | pd.DataFrame | np.ndarray,
    y_pred: np.ndarray,
    targets: list[str],
) -> dict[str, Any]:
    y_pred = np.asarray(y_pred)
    if y_pred.ndim == 1:
        y_pred = y_pred.reshape(-1, 1)

    if isinstance(y_true, pd.DataFrame):
        frame = y_true
    elif isinstance(y_true, pd.Series):
        frame = y_true.to_frame(name=targets[0])
    else:
        frame = pd.DataFrame(np.asarray(y_true), columns=targets)

    per_horizon = {}
    for i, target in enumerate(targets):
        per_horizon[target] = regression_metrics(frame[target].values, y_pred[:, i])
    overall = average_horizon_metrics(per_horizon)
    return {"overall": overall, "per_horizon": per_horizon}

evaluate_multioutput = evaluate_predictions

def _noisy_xy(
    splits: dict[str, Any],
    feature_cols: list[str],
    config: dict[str, Any] | None,
    seed: int,
) -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {}
    for key, seed_offset in (("X_train", 1), ("X_val", 2), ("X_test", 3)):
        frame = splits[key][["city", *feature_cols]].copy()
        out[key] = apply_forecast_weather_noise(
            frame,
            feature_cols,
            config=config,
            seed=seed + seed_offset,
        )
    return out

def train_sklearn_model(
    name: str,
    estimator,
    splits: dict[str, Any],
    feature_cols: list[str],
    targets: list[str],
    config: dict[str, Any] | None = None,
    random_seed: int = 42,
) -> dict[str, Any]:
    preprocess = build_preprocess(feature_cols)
    pipe = Pipeline([("preprocess", preprocess), ("model", estimator)])

    noisy = _noisy_xy(splits, feature_cols, config, random_seed)
    X_train, X_val, X_test = noisy["X_train"], noisy["X_val"], noisy["X_test"]

    y_train = splits["y_train"][targets[0]] if len(targets) == 1 else splits["y_train"]
    pipe.fit(X_train, y_train)
    val_pred = pipe.predict(X_val)
    test_pred = pipe.predict(X_test)

    val_metrics = evaluate_predictions(splits["y_val"], val_pred, targets)
    test_metrics = evaluate_predictions(splits["y_test"], test_pred, targets)

    y_val_arr = splits["y_val"][targets[0]].values
    interval_level = float((config or {}).get("prediction_interval_level", 0.8))
    interval = residual_prediction_interval(y_val_arr, np.asarray(val_pred).reshape(-1), interval_level)

    baseline = None
    if "aqi" in feature_cols:
        baseline = {
            "val": persistence_metrics(y_val_arr, splits["X_val"]["aqi"].values),
            "test": persistence_metrics(
                splits["y_test"][targets[0]].values,
                splits["X_test"]["aqi"].values,
            ),
        }

    return {
        "name": name,
        "type": "sklearn",
        "model": pipe,
        "feature_cols": feature_cols,
        "targets": targets,
        "val_metrics": val_metrics,
        "test_metrics": test_metrics,
        "val_rmse": val_metrics["overall"]["rmse"],
        "prediction_interval": interval,
        "persistence_baseline": baseline,
    }

def build_lstm_sequences(
    X: pd.DataFrame,
    y: pd.DataFrame,
    feature_cols: list[str],
    seq_len: int = 24,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    xs, ys, cities = [], [], []
    city_codes = {c: i for i, c in enumerate(sorted(X["city"].unique()))}
    work = X.copy()
    work[feature_cols] = work[feature_cols].astype(float)
    for city, idx in work.groupby("city").groups.items():
        Xi = work.loc[idx, feature_cols].values
        yi = y.loc[idx].values
        if len(Xi) <= seq_len:
            continue
        for i in range(seq_len, len(Xi)):
            xs.append(Xi[i - seq_len : i])
            ys.append(yi[i])
            cities.append(city_codes[city])
    if not xs:
        n_out = int(y.shape[1]) if getattr(y, "ndim", 1) > 1 else 1
        return np.empty((0, seq_len, len(feature_cols))), np.empty((0, n_out)), np.empty((0,))
    return np.asarray(xs, dtype=np.float32), np.asarray(ys, dtype=np.float32), np.asarray(cities)

def train_lstm_model(
    splits: dict[str, Any],
    feature_cols: list[str],
    targets: list[str],
    random_seed: int = 42,
    seq_len: int = 24,
    epochs: int = 12,
    config: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    try:
        import tensorflow as tf
        from tensorflow import keras
        from tensorflow.keras import layers
    except Exception as exc:
        print(f"[train] TensorFlow unavailable, skipping LSTM: {exc}")
        return None

    tf.random.set_seed(random_seed)
    np.random.seed(random_seed)

    def _fill(frame: pd.DataFrame) -> pd.DataFrame:
        out = frame.copy()
        out[feature_cols] = out[feature_cols].replace([np.inf, -np.inf], np.nan)
        out[feature_cols] = out[feature_cols].fillna(out[feature_cols].median(numeric_only=True))
        return out

    noisy = _noisy_xy(splits, feature_cols, config, random_seed)
    X_train = _fill(pd.concat([splits["X_train"][["city"]], noisy["X_train"][feature_cols]], axis=1))
    X_val = _fill(pd.concat([splits["X_val"][["city"]], noisy["X_val"][feature_cols]], axis=1))
    X_test = _fill(pd.concat([splits["X_test"][["city"]], noisy["X_test"][feature_cols]], axis=1))

    xtr, ytr, _ = build_lstm_sequences(X_train, splits["y_train"], feature_cols, seq_len)
    xv, yv, _ = build_lstm_sequences(X_val, splits["y_val"], feature_cols, seq_len)
    xt, yt, _ = build_lstm_sequences(X_test, splits["y_test"], feature_cols, seq_len)

    if len(xtr) < 50 or len(xv) < 10:
        print("[train] Not enough sequence samples for LSTM")
        return None

    mean = xtr.mean(axis=(0, 1), keepdims=True)
    std = xtr.std(axis=(0, 1), keepdims=True) + 1e-6
    xtr = (xtr - mean) / std
    xv = (xv - mean) / std
    xt = (xt - mean) / std

    n_out = len(targets)
    model = keras.Sequential(
        [
            layers.Input(shape=(seq_len, len(feature_cols))),
            layers.LSTM(64, return_sequences=False),
            layers.Dense(32, activation="relu"),
            layers.Dense(n_out),
        ]
    )
    model.compile(optimizer=keras.optimizers.Adam(1e-3), loss="mse")
    model.fit(xtr, ytr, validation_data=(xv, yv), epochs=epochs, batch_size=64, verbose=0)

    val_pred = model.predict(xv, verbose=0)
    test_pred = model.predict(xt, verbose=0)
    if n_out == 1:
        val_pred = val_pred.reshape(-1, 1)
        test_pred = test_pred.reshape(-1, 1)
        yv_df = pd.DataFrame(yv.reshape(-1, 1), columns=targets)
        yt_df = pd.DataFrame(yt.reshape(-1, 1), columns=targets)
    else:
        yv_df = pd.DataFrame(yv, columns=targets)
        yt_df = pd.DataFrame(yt, columns=targets)

    val_metrics = evaluate_predictions(yv_df, val_pred, targets)
    test_metrics = evaluate_predictions(yt_df, test_pred, targets)
    interval_level = float((config or {}).get("prediction_interval_level", 0.8))
    interval = residual_prediction_interval(yv_df[targets[0]].values, val_pred[:, 0], interval_level)

    return {
        "name": "lstm",
        "type": "keras",
        "model": model,
        "scaler_mean": mean,
        "scaler_std": std,
        "seq_len": seq_len,
        "feature_cols": feature_cols,
        "targets": targets,
        "val_metrics": val_metrics,
        "test_metrics": test_metrics,
        "val_rmse": val_metrics["overall"]["rmse"],
        "prediction_interval": interval,
    }
