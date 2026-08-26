from __future__ import annotations

def _tip(
    title: str,
    advice: str,
    actions: list[dict[str, str]],
    level: str,
) -> dict:
    return {
        "title": title,
        "advice": advice,
        "actions": actions,
        "level": level,
    }

HEALTH_TIPS: dict[str, dict] = {
    "Good": _tip(
        "Good air quality",
        "Air looks healthy for most people. Great day for outdoor time — walk, exercise, or open windows for fresh air.",
        [
            {"id": "outdoor", "label": "Outdoor OK", "detail": "Normal outdoor activity is fine"},
            {"id": "windows", "label": "Open windows", "detail": "Fresh air helps if weather allows"},
            {"id": "sensitive", "label": "All groups OK", "detail": "No special limits for sensitive groups"},
        ],
        "good",
    ),
    "Moderate": _tip(
        "Moderate air quality",
        "Most people can go outside as usual. If you have asthma or heart/lung issues, keep long or intense outdoor workouts shorter.",
        [
            {"id": "outdoor", "label": "Outdoor OK", "detail": "Fine for most people"},
            {"id": "sensitive", "label": "Sensitive: ease up", "detail": "Limit long outdoor exertion"},
            {"id": "windows", "label": "Windows OK", "detail": "Air out rooms when convenient"},
        ],
        "moderate",
    ),
    "Unhealthy for Sensitive Groups": _tip(
        "Unhealthy for sensitive groups",
        "Children, older adults, and people with asthma should reduce outdoor exercise. Prefer indoor activity and shorter outdoor trips.",
        [
            {"id": "outdoor", "label": "Limit outdoor", "detail": "Shorter outdoor time, lighter activity"},
            {"id": "sensitive", "label": "Sensitive: take care", "detail": "Kids, elders, asthma — stay cautious"},
            {"id": "windows", "label": "Prefer indoor air", "detail": "Keep busy hours indoors if possible"},
        ],
        "sensitive",
    ),
    "Unhealthy": _tip(
        "Unhealthy air",
        "Limit time outdoors. Wear a well-fitted N95/KN95 if you must go out. Keep windows closed during peak pollution and use cleaner indoor air if you can.",
        [
            {"id": "outdoor", "label": "Limit outdoor", "detail": "Avoid long outdoor stays"},
            {"id": "mask", "label": "Mask recommended", "detail": "N95/KN95 if going outside"},
            {"id": "windows", "label": "Close windows", "detail": "Keep indoor air cleaner"},
        ],
        "unhealthy",
    ),
    "Very Unhealthy": _tip(
        "Very unhealthy air",
        "Avoid outdoor activity when possible. Use a mask outdoors, keep windows closed, and consider an indoor air purifier or a cleaner room.",
        [
            {"id": "outdoor", "label": "Stay indoors", "detail": "Skip outdoor exercise"},
            {"id": "mask", "label": "Mask outdoors", "detail": "N95/KN95 if you must go out"},
            {"id": "windows", "label": "Close windows", "detail": "Purifier helps if available"},
        ],
        "very",
    ),
    "Hazardous": _tip(
        "Hazardous air",
        "Stay indoors and avoid all outdoor exertion. Use a mask only if you must go out briefly. Seek medical help if you feel chest pain or shortness of breath.",
        [
            {"id": "outdoor", "label": "Stay indoors", "detail": "Avoid outdoor exertion completely"},
            {"id": "mask", "label": "Mask if outdoors", "detail": "Only for essential short trips"},
            {"id": "sensitive", "label": "Watch symptoms", "detail": "Get help if breathing feels hard"},
        ],
        "hazard",
    ),
    "Unknown": _tip(
        "Air quality unknown",
        "Check back soon for the latest forecast and guidance for your city.",
        [
            {"id": "outdoor", "label": "Check again soon", "detail": "Guidance updates with the forecast"},
        ],
        "unknown",
    ),
}

def health_tip_for_aqi_category(category: str | None) -> dict:
    if not category:
        return HEALTH_TIPS["Unknown"]
    return HEALTH_TIPS.get(category, HEALTH_TIPS["Unknown"])
