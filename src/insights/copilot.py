from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx

from src.inference.predict import (
    alerts_for_city,
    current_weather_for_city,
    history_for_city,
    predict_city,
)
from src.insights.creative import exercise_advice, smog_season_calendar
from src.utils.config import get_project_root
from src.utils.health_tips import health_tip_for_aqi_category

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")

SUGGESTIONS = [
    "Is outdoor exercise OK today?",
    "Will air improve in 24 hours?",
    "When is smog season worst?",
    "What is driving AQI in SHAP?",
    "How has the last week looked?",
]


def _safe(fn, default: Any = None) -> Any:
    try:
        return fn()
    except Exception:
        return default


def _history_summary(city: str, config: dict[str, Any]) -> dict[str, Any] | None:
    points = history_for_city(city, hours=168, config=config)
    vals = [float(p["aqi"]) for p in points if p.get("aqi") is not None]
    if not vals:
        return None
    n = len(vals)
    first = vals[: max(1, n // 3)]
    last = vals[-max(1, n // 3) :]
    first_avg = sum(first) / len(first)
    last_avg = sum(last) / len(last)
    if last_avg > first_avg + 8:
        trend = "worsening"
    elif last_avg < first_avg - 8:
        trend = "improving"
    else:
        trend = "fairly steady"
    peak = max(points, key=lambda p: p.get("aqi") if p.get("aqi") is not None else -1)
    low = min(points, key=lambda p: p.get("aqi") if p.get("aqi") is not None else 1e9)
    return {
        "hours_covered": n,
        "start": points[0].get("event_time"),
        "end": points[-1].get("event_time"),
        "latest_aqi": vals[-1],
        "mean_aqi": round(sum(vals) / n, 1),
        "min_aqi": round(min(vals), 1),
        "max_aqi": round(max(vals), 1),
        "trend": trend,
        "peak_time": peak.get("event_time"),
        "peak_aqi": peak.get("aqi"),
        "low_time": low.get("event_time"),
        "low_aqi": low.get("aqi"),
    }


def _smog_summary(config: dict[str, Any]) -> dict[str, Any] | None:
    smog = smog_season_calendar(config)
    if not smog:
        return None
    months = smog.get("months") or []
    ranked = sorted(months, key=lambda m: float(m.get("mean_aqi") or 0), reverse=True)
    return {
        "peak_smog_label": smog.get("peak_smog_label"),
        "peak_smog_months": smog.get("peak_smog_months"),
        "in_peak_season": smog.get("in_peak_season"),
        "headline": smog.get("headline"),
        "summary": smog.get("summary"),
        "peak_month": (smog.get("peak_month") or {}).get("label"),
        "peak_mean_aqi": (smog.get("peak_month") or {}).get("mean_aqi"),
        "cleanest_month": (smog.get("cleanest_month") or {}).get("label"),
        "cleanest_mean_aqi": (smog.get("cleanest_month") or {}).get("mean_aqi"),
        "findings": (smog.get("findings") or [])[:3],
        "monthly_means": [
            {"month": m.get("label"), "mean_aqi": m.get("mean_aqi"), "peak": bool(m.get("is_peak_smog"))}
            for m in ranked[:6]
        ],
    }


def _shap_summary(city: str, config: dict[str, Any]) -> dict[str, Any] | None:
    from src.inference.explain import explain_city, global_shap_summary

    pack = explain_city(city, config, horizon_hours=24, include_all_horizons=False)
    if not pack:
        return None
    signed = pack.get("local_signed") or pack.get("local_features") or []
    top = []
    for row in signed[:5]:
        top.append(
            {
                "feature": row.get("feature") or row.get("name"),
                "impact": row.get("contribution") or row.get("shap") or row.get("importance"),
                "direction": row.get("direction") or row.get("effect"),
            }
        )
    global_pack = _safe(lambda: global_shap_summary(config), {}) or {}
    global_top = []
    for row in (global_pack.get("top_features") or global_pack.get("features") or [])[:5]:
        if isinstance(row, dict):
            global_top.append(
                {
                    "feature": row.get("feature") or row.get("name"),
                    "importance": row.get("mean_abs_shap") or row.get("importance") or row.get("value"),
                }
            )
        else:
            global_top.append({"feature": str(row)})
    return {
        "available": bool(pack.get("available")),
        "horizon_hours": pack.get("horizon_hours") or 24,
        "model": pack.get("model"),
        "prediction": pack.get("prediction"),
        "narrative": (pack.get("narrative") or "")[:400],
        "top_local_drivers": top,
        "pollutant_link": pack.get("pollutant_link"),
        "global_top_drivers": global_top,
        "note": pack.get("note"),
    }


def _leaderboard_summary(city: str, config: dict[str, Any]) -> dict[str, Any] | None:
    root = get_project_root()
    path = root / config.get("storage", {}).get("leaderboard_path", "artifacts/model_leaderboard.json")
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    horizons = []
    for h, meta in (data.get("horizon_winners") or {}).items():
        val = ((meta.get("val") or {}).get("overall")) or {}
        horizons.append(
            {
                "horizon_hours": int(h),
                "model": meta.get("name"),
                "val_mae": round(float(val.get("mae") or 0), 2) if val.get("mae") is not None else None,
                "val_r2": round(float(val.get("r2") or 0), 3) if val.get("r2") is not None else None,
                "val_category_acc": (
                    round(float(val.get("category_accuracy") or 0) * 100, 1)
                    if val.get("category_accuracy") is not None
                    else None
                ),
            }
        )
    horizons.sort(key=lambda x: x["horizon_hours"])

    city_acc = None
    mon_path = root / "artifacts" / "monitoring" / "summary.json"
    if mon_path.exists():
        mon = json.loads(mon_path.read_text(encoding="utf-8"))
        city_row = (mon.get("by_city") or {}).get(city)
        if city_row:
            city_acc = {
                "mae": round(float(city_row.get("mae") or 0), 2),
                "category_accuracy_pct": round(float(city_row.get("category_accuracy") or 0) * 100, 1),
                "scored_rows": city_row.get("n"),
            }
        overall = mon.get("overall") or {}
        live_overall = {
            "mae": round(float(overall.get("mae") or 0), 2) if overall.get("mae") is not None else None,
            "category_accuracy_pct": (
                round(float(overall.get("category_accuracy") or 0) * 100, 1)
                if overall.get("category_accuracy") is not None
                else None
            ),
            "scored_rows": overall.get("n"),
        }
    else:
        live_overall = None

    return {
        "winner": data.get("winner"),
        "trained_at": data.get("trained_at"),
        "horizon_winners": horizons,
        "city_live_accuracy": city_acc,
        "overall_live_accuracy": live_overall,
    }


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
            {
                "when": a.get("when"),
                "aqi": a.get("aqi"),
                "category": a.get("category"),
                "message": a.get("message"),
            }
            for a in (alerts.get("alerts") or [])[:3]
        ],
        "history": _safe(lambda: _history_summary(city, config)),
        "smog_season": _safe(lambda: _smog_summary(config)),
        "shap": None,
        "models": _safe(lambda: _leaderboard_summary(city, config)),
    }


def _enrich_shap(ctx: dict[str, Any], city: str, config: dict[str, Any]) -> None:
    ctx["shap"] = _safe(lambda: _shap_summary(city, config))


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

    hist = ctx.get("history") or {}
    if hist:
        lines.append(
            f"Recent history (~{hist.get('hours_covered')}h): mean={hist.get('mean_aqi')} "
            f"min={hist.get('min_aqi')} max={hist.get('max_aqi')} trend={hist.get('trend')} "
            f"latest={hist.get('latest_aqi')} peak={hist.get('peak_aqi')}@{hist.get('peak_time')} "
            f"low={hist.get('low_aqi')}@{hist.get('low_time')}"
        )

    smog = ctx.get("smog_season") or {}
    if smog:
        lines.append(
            f"Smog season: {smog.get('headline')}. Window={smog.get('peak_smog_label')}. "
            f"In peak now={smog.get('in_peak_season')}. {smog.get('summary')}"
        )
        if smog.get("monthly_means"):
            bits = ", ".join(
                f"{m['month']}={m['mean_aqi']}{'*' if m.get('peak') else ''}"
                for m in smog["monthly_means"]
            )
            lines.append(f"Highest months (*peak window): {bits}")
        if smog.get("findings"):
            lines.append("EDA findings: " + "; ".join(str(x) for x in smog["findings"]))

    shap = ctx.get("shap") or {}
    if shap:
        lines.append(
            f"SHAP (+{shap.get('horizon_hours')}h): available={shap.get('available')} "
            f"model={shap.get('model')} prediction={shap.get('prediction')}"
        )
        if shap.get("narrative"):
            lines.append(f"SHAP narrative: {shap.get('narrative')}")
        if shap.get("top_local_drivers"):
            bits = ", ".join(
                f"{d.get('feature')}={d.get('impact')}({d.get('direction') or ''})"
                for d in shap["top_local_drivers"]
                if d.get("feature")
            )
            if bits:
                lines.append(f"Top local SHAP drivers: {bits}")
        if shap.get("global_top_drivers"):
            bits = ", ".join(
                f"{d.get('feature')}={d.get('importance')}"
                for d in shap["global_top_drivers"]
                if d.get("feature")
            )
            if bits:
                lines.append(f"Global SHAP drivers: {bits}")

    models = ctx.get("models") or {}
    if models:
        lines.append(f"Leaderboard winner: {models.get('winner')} (trained {models.get('trained_at')})")
        for h in models.get("horizon_winners") or []:
            lines.append(
                f"Horizon +{h.get('horizon_hours')}h model={h.get('model')} "
                f"val_mae={h.get('val_mae')} val_r2={h.get('val_r2')} "
                f"cat_acc%={h.get('val_category_acc')}"
            )
        if models.get("city_live_accuracy"):
            c = models["city_live_accuracy"]
            lines.append(
                f"Live accuracy for {ctx.get('city')}: MAE={c.get('mae')} "
                f"category_acc%={c.get('category_accuracy_pct')} n={c.get('scored_rows')}"
            )
        if models.get("overall_live_accuracy"):
            o = models["overall_live_accuracy"]
            lines.append(
                f"Overall live accuracy: MAE={o.get('mae')} "
                f"category_acc%={o.get('category_accuracy_pct')} n={o.get('scored_rows')}"
            )

    return "\n".join(lines)


def _fallback_reply(message: str, ctx: dict[str, Any]) -> str:
    q = (message or "").lower()
    city = ctx.get("city") or "this city"
    aqi = ctx.get("current_aqi")
    cat = ctx.get("current_category") or "Unknown"
    tip = (ctx.get("health_tip") or {}).get("advice") or "Follow local health guidance."
    ex = ctx.get("exercise") or {}
    f24 = next((f for f in (ctx.get("forecast") or []) if f.get("horizon_hours") == 24), None)
    aqi_label = f"{aqi}" if aqi is not None else "—"
    smog = ctx.get("smog_season") or {}
    hist = ctx.get("history") or {}
    shap = ctx.get("shap") or {}
    models = ctx.get("models") or {}

    if any(k in q for k in ("smog", "season", "month", "winter", "october", "november", "december")):
        return (
            f"**Smog season · Pakistan**\n\n"
            f"**Window:** {smog.get('peak_smog_label') or 'Oct – Feb'}\n"
            f"**Now:** {smog.get('headline') or 'See the smog panel for details'}\n\n"
            f"- {smog.get('summary') or tip}\n"
            f"- Peak month ~ {smog.get('peak_month')} ({smog.get('peak_mean_aqi')} AQI); "
            f"cleanest ~ {smog.get('cleanest_month')} ({smog.get('cleanest_mean_aqi')} AQI)"
        )
    if any(k in q for k in ("history", "week", "trend", "past", "recent days", "last 7")):
        if hist:
            return (
                f"**Recent history · {city}**\n\n"
                f"**Latest:** AQI {hist.get('latest_aqi')} · mean {hist.get('mean_aqi')}\n"
                f"**Range:** {hist.get('min_aqi')} – {hist.get('max_aqi')} ({hist.get('trend')})\n\n"
                f"- Peak ~ {hist.get('peak_aqi')} at {hist.get('peak_time')}\n"
                f"- Low ~ {hist.get('low_aqi')} at {hist.get('low_time')}"
            )
    if any(k in q for k in ("shap", "explain", "driver", "feature", "why model", "xai")):
        narrative = shap.get("narrative") or "SHAP detail is loading from the experts panel."
        drivers = shap.get("top_local_drivers") or []
        driver_bits = [
            f"{d.get('feature')}"
            for d in drivers[:3]
            if d.get("feature")
        ]
        return (
            f"**Model drivers · {city}**\n\n"
            f"**Horizon:** +{shap.get('horizon_hours') or 24}h · model {shap.get('model') or '—'}\n\n"
            f"- {narrative}\n"
            + (f"- Top features: {', '.join(driver_bits)}\n" if driver_bits else "")
            + f"- Live pollutant signal: {(ctx.get('weather') or {}).get('pollutant_driver') or 'n/a'}"
        )
    if any(k in q for k in ("leaderboard", "model", "accuracy", "mae", "ridge", "winner", "experts")):
        wins = models.get("horizon_winners") or []
        win_lines = [
            f"+{h.get('horizon_hours')}h → {h.get('model')} (MAE {h.get('val_mae')})"
            for h in wins
        ]
        city_acc = models.get("city_live_accuracy") or {}
        return (
            f"**Models & accuracy · {city}**\n\n"
            f"**Winner pack:** {models.get('winner') or '—'}\n\n"
            + ("\n".join(f"- {line}" for line in win_lines) if win_lines else "- Leaderboard not loaded")
            + (
                f"\n- Live city MAE {city_acc.get('mae')}, "
                f"category accuracy {city_acc.get('category_accuracy_pct')}%"
                if city_acc
                else ""
            )
        )
    if any(k in q for k in ("jog", "run", "exercise", "workout", "walk", "sport")):
        return (
            f"**Exercise guidance · {city}**\n\n"
            f"**Now:** AQI {aqi_label} ({cat})\n\n"
            f"- {ex.get('headline') or 'Check conditions before training outdoors.'}\n"
            f"- {ex.get('detail') or tip}"
        )
    if any(k in q for k in ("tomorrow", "24", "improve", "worse", "forecast", "next")):
        if f24:
            return (
                f"**24-hour outlook · {city}**\n\n"
                f"**Now:** AQI {aqi_label} ({cat})\n"
                f"**+24h:** AQI {f24.get('aqi')} ({f24.get('category')})\n\n"
                f"- {tip}"
            )
        return (
            f"**Air status · {city}**\n\n"
            f"**Now:** AQI {aqi_label} ({cat})\n\n"
            f"- {tip}"
        )
    if any(k in q for k in ("mask", "window", "kids", "child", "asthma", "sensitive", "do now", "advice")):
        return (
            f"**What to do · {city}**\n\n"
            f"**Now:** AQI {aqi_label} ({cat})\n\n"
            f"- {tip}"
        )
    if any(k in q for k in ("why", "pollutant", "pm2", "pm10", "cause")):
        driver = (ctx.get("weather") or {}).get("pollutant_driver") or "recent pollution and weather"
        return (
            f"**What’s driving the air · {city}**\n\n"
            f"**Now:** AQI {aqi_label} ({cat})\n\n"
            f"- Main driver signal: {driver}\n"
            f"- {tip}"
        )
    return (
        f"**Air status · {city}**\n\n"
        f"**Now:** AQI {aqi_label} ({cat})\n\n"
        f"- {tip}\n"
        f"- Ask about exercise, forecast, smog season, history, SHAP drivers, or model accuracy."
    )


def _call_groq(message: str, ctx: dict[str, Any], api_key: str) -> str:
    system = (
        "You are AtmoVista Copilot, a professional air-quality assistant for Pakistan cities. "
        "Answer only from the provided live AtmoVista context (forecast, weather, tips, history, "
        "smog season, SHAP/XAI, leaderboard, live accuracy). Do not invent readings. "
        "Do not claim to be a doctor.\n\n"
        "Format every reply for high readability using this structure:\n"
        "1) One short bold title line\n"
        "2) A blank line, then 1–2 bold status lines\n"
        "3) A blank line, then 2–5 bullet points starting with '- '\n"
        "Keep it concise. Prefer bullets over long paragraphs. No emoji. No markdown tables."
    )
    user = (
        f"Live AtmoVista context:\n{_context_prompt(ctx)}\n\n"
        f"User question: {message.strip()}"
    )
    payload = {
        "model": GROQ_MODEL,
        "temperature": 0.25,
        "max_tokens": 480,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=45.0) as client:
        res = client.post(GROQ_URL, headers=headers, json=payload)
        if res.status_code >= 400:
            detail = ""
            try:
                err = res.json()
                detail = str(
                    ((err.get("error") or {}) if isinstance(err, dict) else {}).get("message")
                    or err
                )[:180]
            except Exception:
                detail = (res.text or "")[:180]
            raise RuntimeError(f"HTTP {res.status_code}: {detail or res.reason_phrase}")
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
    _enrich_shap(ctx, city, cfg)
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
                "suggestions": SUGGESTIONS,
            }
        except Exception as exc:
            reply = _fallback_reply(text, ctx)
            err_msg = str(exc).strip()[:200] or type(exc).__name__
            return {
                "city": city,
                "reply": reply,
                "provider": "fallback",
                "model": None,
                "fallback": True,
                "note": f"Groq unavailable ({err_msg}); used local guidance.",
                "suggestions": SUGGESTIONS,
            }

    return {
        "city": city,
        "reply": _fallback_reply(text, ctx),
        "provider": "fallback",
        "model": None,
        "fallback": True,
        "note": "Set GROQ_API_KEY for full AI answers. Showing local guidance from AtmoVista data.",
        "suggestions": SUGGESTIONS,
    }
