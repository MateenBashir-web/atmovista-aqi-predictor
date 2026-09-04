from __future__ import annotations

import os
import re
from typing import Any

import httpx

from src.inference.predict import alerts_for_city, current_weather_for_city, predict_city
from src.insights.creative import exercise_advice
from src.utils.health_tips import health_tip_for_aqi_category

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")


def _build_context(city: str, config: dict[str, Any]) -> dict[str, Any]:
    pred = predict_city(city, config)
    weather = current_weather_for_city(city, config)
    alerts = alerts_for_city(city, config)
    tip = health_tip_for_aqi_category(pred.get("current_category") or "Unknown")
    f24 = next((f for f in pred.get("forecast", []) if f.get("horizon_hours") == 24), None)
    exercise = exercise_advice(
        pred.get("current_aqi"),
        pred.get("current_category"),
        f24.get("aqi") if f24 else None,
        f24.get("category") if f24 else None,
    )
    forecast_bits = [
        {
            "horizon_hours": f.get("horizon_hours"),
            "aqi": f.get("aqi"),
            "category": f.get("category"),
        }
        for f in (pred.get("forecast") or [])[:3]
    ]
    pollutants = [
        {
            "label": p.get("label"),
            "value": p.get("value"),
            "dominant": p.get("is_dominant"),
        }
        for p in (weather.get("pollutants") or [])[:4]
    ]
    return {
        "city": city,
        "current_aqi": pred.get("current_aqi"),
        "current_category": pred.get("current_category"),
        "event_time": pred.get("event_time"),
        "forecast": forecast_bits,
        "weather": {
            "temperature_c": weather.get("temperature_c"),
            "humidity_pct": weather.get("humidity_pct"),
            "wind_kph": weather.get("wind_kph"),
            "pollutant_driver": weather.get("pollutant_driver"),
            "air_driver": weather.get("air_driver"),
        },
        "pollutants": pollutants,
        "health_tip": {
            "title": tip.get("title") if isinstance(tip, dict) else None,
            "advice": tip.get("advice") if isinstance(tip, dict) else str(tip),
        },
        "exercise": {
            "verdict": exercise.get("verdict"),
            "headline": exercise.get("title") or exercise.get("headline"),
            "detail": " ".join(
                str(x)
                for x in (exercise.get("reason"), exercise.get("recommendation"))
                if x
            )
            or exercise.get("detail"),
        },
        "alerts": [
            {"when": a.get("when"), "aqi": a.get("aqi"), "category": a.get("category"), "message": a.get("message")}
            for a in (alerts.get("alerts") or [])[:3]
        ],
    }


def _context_prompt(ctx: dict[str, Any]) -> str:
    lines = [
        f"City: {ctx['city']}",
        f"Current AQI: {ctx.get('current_aqi')} ({ctx.get('current_category')})",
        f"Observation time: {ctx.get('event_time')}",
    ]
    for f in ctx.get("forecast") or []:
        lines.append(f"+{f['horizon_hours']}h forecast: AQI {f.get('aqi')} ({f.get('category')})")
    w = ctx.get("weather") or {}
    lines.append(
        f"Weather: temp={w.get('temperature_c')}C humidity={w.get('humidity_pct')}% "
        f"wind={w.get('wind_kph')} kph driver={w.get('pollutant_driver') or w.get('air_driver')}"
    )
    if ctx.get("pollutants"):
        bits = ", ".join(
            f"{p['label']}={p['value']}{'*' if p.get('dominant') else ''}" for p in ctx["pollutants"]
        )
        lines.append(f"Pollutants (*dominant): {bits}")
    tip = ctx.get("health_tip") or {}
    if tip.get("advice"):
        lines.append(f"Health tip: {tip.get('title') or ''} — {tip.get('advice')}")
    ex = ctx.get("exercise") or {}
    if ex.get("verdict"):
        lines.append(f"Exercise: {ex.get('verdict')} — {ex.get('headline')}. {ex.get('detail')}")
    alerts = ctx.get("alerts") or []
    if alerts:
        lines.append("Alerts: " + "; ".join(f"{a.get('when')}: {a.get('message')}" for a in alerts))
    else:
        lines.append("Alerts: none")
    return "\n".join(lines)


def _fallback_reply(message: str, ctx: dict[str, Any]) -> str:
    q = (message or "").lower()
    city = ctx.get("city") or "this city"
    aqi = ctx.get("current_aqi")
    cat = ctx.get("current_category") or "Unknown"
    tip = (ctx.get("health_tip") or {}).get("advice") or "Follow local health guidance."
    ex = ctx.get("exercise") or {}
    f24 = next((f for f in (ctx.get("forecast") or []) if f.get("horizon_hours") == 24), None)

    if any(k in q for k in ("jog", "run", "exercise", "workout", "walk", "sport")):
        return (
            f"For {city} right now (AQI {aqi}, {cat}): {ex.get('headline') or tip}. "
            f"{ex.get('detail') or ''}".strip()
        )
    if any(k in q for k in ("tomorrow", "24", "improve", "worse", "forecast", "next")):
        if f24:
            return (
                f"In {city}, the +24h outlook is about AQI {f24.get('aqi')} ({f24.get('category')}). "
                f"Current level is {aqi} ({cat}). {tip}"
            )
        return f"Current AQI in {city} is {aqi} ({cat}). {tip}"
    if any(k in q for k in ("mask", "window", "kids", "child", "asthma", "sensitive", "do now", "advice")):
        return f"For {city} (AQI {aqi}, {cat}): {tip}"
    if any(k in q for k in ("why", "pollutant", "pm2", "pm10", "cause")):
        driver = (ctx.get("weather") or {}).get("pollutant_driver") or "recent pollution and weather"
        return f"In {city}, air is currently {cat} (AQI {aqi}). Main driver signal: {driver}. {tip}"
    return (
        f"{city} is currently AQI {aqi} ({cat}). {tip} "
        f"Ask about exercise, tomorrow's outlook, or what to do now."
    )


def _call_groq(message: str, ctx: dict[str, Any], api_key: str) -> str:
    system = (
        "You are AtmoVista Copilot, a helpful air-quality assistant for Pakistan cities. "
        "Answer only from the provided live AtmoVista context. Be concise (3-6 short sentences). "
        "Give practical advice for outdoor activity, masks, windows, and sensitive groups. "
        "Do not invent sensor readings. Do not claim to be a doctor. "
        "If unsure, say so and stick to the context numbers."
    )
    user = (
        f"Live AtmoVista context:\n{_context_prompt(ctx)}\n\n"
        f"User question: {message.strip()}"
    )
    payload = {
        "model": GROQ_MODEL,
        "temperature": 0.3,
        "max_tokens": 350,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=25.0) as client:
        res = client.post(GROQ_URL, headers=headers, json=payload)
        res.raise_for_status()
        data = res.json()
    content = (((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()
    if not content:
        raise RuntimeError("Empty model response")
    content = re.sub(r"\n{3,}", "\n\n", content)
    return content


def ask_copilot(city: str, message: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
    from src.utils.config import load_config

    cfg = config or load_config()
    text = (message or "").strip()
    if not text:
        raise ValueError("message is required")
    if len(text) > 500:
        text = text[:500]

    ctx = _build_context(city, cfg)
    api_key = (os.getenv("GROQ_API_KEY") or "").strip()
    if api_key:
        try:
            reply = _call_groq(text, ctx, api_key)
            return {
                "city": city,
                "reply": reply,
                "provider": "groq",
                "model": GROQ_MODEL,
                "fallback": False,
                "suggestions": [
                    "Is outdoor exercise OK today?",
                    "Will air improve in 24 hours?",
                    "What should I do right now?",
                ],
            }
        except Exception as exc:
            reply = _fallback_reply(text, ctx)
            return {
                "city": city,
                "reply": reply,
                "provider": "fallback",
                "model": None,
                "fallback": True,
                "note": f"Groq unavailable ({type(exc).__name__}); used local guidance.",
                "suggestions": [
                    "Is outdoor exercise OK today?",
                    "Will air improve in 24 hours?",
                    "What should I do right now?",
                ],
            }

    return {
        "city": city,
        "reply": _fallback_reply(text, ctx),
        "provider": "fallback",
        "model": None,
        "fallback": True,
        "note": "Set GROQ_API_KEY for full AI answers. Showing local guidance from AtmoVista data.",
        "suggestions": [
            "Is outdoor exercise OK today?",
            "Will air improve in 24 hours?",
            "What should I do right now?",
        ],
    }
