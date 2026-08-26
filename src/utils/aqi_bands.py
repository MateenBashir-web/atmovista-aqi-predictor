from __future__ import annotations

from typing import Any

AQI_BANDS: list[dict[str, Any]] = [
    {"name": "Good", "min": 0, "max": 50, "color": "#22c55e"},
    {"name": "Moderate", "min": 51, "max": 100, "color": "#eab308"},
    {"name": "Unhealthy for Sensitive Groups", "min": 101, "max": 150, "color": "#f97316"},
    {"name": "Unhealthy", "min": 151, "max": 200, "color": "#ef4444"},
    {"name": "Very Unhealthy", "min": 201, "max": 300, "color": "#a855f7"},
    {"name": "Hazardous", "min": 301, "max": 500, "color": "#7f1d1d"},
]

def aqi_category(aqi: float | int | None) -> str:
    if aqi is None:
        return "Unknown"
    value = float(aqi)
    for band in AQI_BANDS:
        if band["min"] <= value <= band["max"]:
            return band["name"]
    if value > 500:
        return "Hazardous"
    return "Unknown"

def aqi_color(aqi: float | int | None) -> str:
    if aqi is None:
        return "#94a3b8"
    value = float(aqi)
    for band in AQI_BANDS:
        if band["min"] <= value <= band["max"]:
            return band["color"]
    return "#7f1d1d"

def is_hazardous_alert(aqi: float | int | None, unhealthy_threshold: int = 151) -> bool:
    if aqi is None:
        return False
    return float(aqi) >= unhealthy_threshold
