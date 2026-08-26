from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.inference.predict import (
    alerts_for_city,
    current_weather_for_city,
    history_for_city,
    load_winner,
    predict_city,
)
from src.inference.explain import explain_city
from src.insights.creative import (
    exercise_advice,
    explain_aqi,
    persistence_baseline_report,
    pipeline_health,
    smog_season_calendar,
)
from src.monitoring.forecast_log import get_monitoring_summary
from src.utils.aqi_bands import AQI_BANDS
from src.utils.config import get_project_root, load_config
from src.utils.health_tips import health_tip_for_aqi_category
from src.utils.storage import load_features, local_feature_path, resolve_storage_mode

config = load_config()
app = FastAPI(title="AtmoVista AQI API", version="1.1.0")

@app.on_event("startup")
def _warm_inference_cache() -> None:
    import threading

    def _warm() -> None:
        try:
            load_winner(config)
            print("[startup] winner models loaded")
        except Exception as exc:
            print(f"[startup] model warmup skipped: {exc}")

    threading.Thread(target=_warm, name="cache-warmup", daemon=True).start()

_raw_origins = __import__("os").getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,https://atmovista.vercel.app",
)
origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]
if origins == ["*"]:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    if "https://atmovista.vercel.app" not in origins:
        origins.append("https://atmovista.vercel.app")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_origin_regex=r"https://.*\.vercel\.app",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

def _known_cities() -> list[str]:
    return [c["name"] for c in config["cities"]]

def _validate_city(city: str) -> str:
    known = _known_cities()
    match = next((c for c in known if c.lower() == city.lower()), None)
    if not match:
        raise HTTPException(status_code=404, detail=f"Unknown city. Choose from: {known}")
    return match

@app.get("/health")
def health():
    return {"status": "ok", "project": config.get("project_name")}

@app.get("/cities")
def cities():
    return {
        "cities": [
            {"name": c["name"], "country": c.get("country", "Pakistan"), "lat": c["lat"], "lon": c["lon"]}
            for c in config["cities"]
        ]
    }

@app.get("/aqi/bands")
def bands():
    return {"bands": AQI_BANDS}

@app.get("/aqi/current")
def current(city: str = Query(..., description="Pakistan city name")):
    city = _validate_city(city)
    try:
        pred = predict_city(city, config)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {
        "city": pred["city"],
        "event_time": pred["event_time"],
        "aqi": pred["current_aqi"],
        "category": pred["current_category"],
        "color": pred["current_color"],
        "model": pred["model"],
    }

@app.get("/aqi/forecast")
def forecast(city: str = Query(...)):
    city = _validate_city(city)
    try:
        return predict_city(city, config)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

@app.get("/aqi/snapshots")
def snapshots():
    rows: dict[str, dict] = {}
    for name in _known_cities():
        try:
            pred = predict_city(name, config)
            rows[name] = {
                "city": name,
                "current_aqi": pred.get("current_aqi"),
                "current_category": pred.get("current_category"),
                "current_color": pred.get("current_color"),
                "event_time": pred.get("event_time"),
            }
        except Exception:
            continue
    return {"snapshots": rows}

@app.get("/aqi/history")
def history(city: str = Query(...), hours: int = Query(168, ge=24, le=720)):
    city = _validate_city(city)
    try:
        return {"city": city, "hours": hours, "points": history_for_city(city, hours=hours, config=config)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

@app.get("/aqi/weather")
def weather(city: str = Query(...)):
    city = _validate_city(city)
    try:
        return current_weather_for_city(city, config)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

@app.get("/aqi/explain")
def explain(city: str = Query("Lahore")):
    city = _validate_city(city)
    try:
        return explain_city(city, config)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

@app.get("/aqi/alerts")
def alerts(city: str = Query(...)):
    city = _validate_city(city)
    try:
        return alerts_for_city(city, config)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

@app.get("/models/leaderboard")
def leaderboard():
    path = get_project_root() / config["storage"]["leaderboard_path"]
    if not path.exists():
        return {"available": False, "models": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    data["available"] = True
    return data

@app.get("/aqi/health-tips")
def health_tips(city: str = Query(...)):
    city = _validate_city(city)
    try:
        pred = predict_city(city, config)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    category = pred["current_category"]
    tip = health_tip_for_aqi_category(category)
    forecast_tips = [
        {
            "horizon_hours": item["horizon_hours"],
            "category": item["category"],
            **health_tip_for_aqi_category(item["category"]),
        }
        for item in pred["forecast"]
    ]
    return {
        "city": city,
        "current_category": category,
        "current": tip,
        "forecast_tips": forecast_tips,
    }

@app.get("/ops/status")
def ops_status():
    root = get_project_root()
    leaderboard_path = root / config["storage"]["leaderboard_path"]
    winner_path = root / config["storage"]["model_dir"] / "winner.json"
    features_path = local_feature_path(config)

    trained_at = None
    winner = None
    if winner_path.exists():
        winner_meta = json.loads(winner_path.read_text(encoding="utf-8"))
        trained_at = winner_meta.get("trained_at")
        winner = winner_meta.get("name")
    elif leaderboard_path.exists():
        board = json.loads(leaderboard_path.read_text(encoding="utf-8"))
        trained_at = board.get("trained_at")
        winner = board.get("winner")

    feature_updated_at = None
    if features_path.exists():
        feature_updated_at = features_path.stat().st_mtime

    return {
        "storage_mode": resolve_storage_mode(config),
        "winner_model": winner,
        "last_train_at": trained_at,
        "features_path": str(features_path) if features_path.exists() else None,
        "features_updated_at": feature_updated_at,
        "cities": _known_cities(),
    }

@app.get("/ops/monitoring")
def ops_monitoring(city: str | None = Query(default=None)):
    try:
        summary = get_monitoring_summary(config)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if city:
        city = _validate_city(city)
        recent = [r for r in summary.get("recent", []) if r.get("city") == city]
        by_city = (summary.get("by_city") or {}).get(city)
        return {**summary, "city": city, "city_stats": by_city, "recent": recent}
    return summary

@app.get("/insights/smog-season")
def insights_smog_season():
    return smog_season_calendar(config)

@app.get("/insights/explain-aqi")
def insights_explain_aqi(
    aqi: float | None = Query(default=None),
    category: str | None = Query(default=None),
    city: str | None = Query(default=None),
):
    if city and aqi is None:
        city = _validate_city(city)
        try:
            pred = predict_city(city, config)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return explain_aqi(pred.get("current_aqi"), pred.get("current_category"))
    return explain_aqi(aqi, category)

@app.get("/insights/exercise")
def insights_exercise(city: str = Query(...)):
    city = _validate_city(city)
    try:
        pred = predict_city(city, config)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    f24 = next((f for f in pred.get("forecast", []) if f.get("horizon_hours") == 24), None)
    advice = exercise_advice(
        pred.get("current_aqi"),
        pred.get("current_category"),
        f24.get("aqi") if f24 else None,
        f24.get("category") if f24 else None,
    )
    return {"city": city, **advice}

@app.get("/ops/baseline")
def ops_baseline():
    return persistence_baseline_report(config)

@app.get("/ops/pipeline")
def ops_pipeline():
    return pipeline_health(config)
