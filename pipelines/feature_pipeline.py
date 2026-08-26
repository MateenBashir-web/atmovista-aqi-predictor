
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.openmeteo import fetch_all_cities_raw
from src.features.engineering import engineer_features
from src.utils.config import load_config
from src.utils.storage import save_features

def run_feature_pipeline(past_days: int = 3) -> dict:
    config = load_config()
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=past_days)

    print(f"[feature] Fetching Open-Meteo data for {len(config['cities'])} cities ({start} -> {end})")
    raw = fetch_all_cities_raw(config["cities"], start=start, end=end)
    if raw.empty:
        raise RuntimeError("No raw data returned from Open-Meteo")

    print(f"[feature] Raw rows: {len(raw)}")
    features = engineer_features(
        raw,
        horizons_hours=config["horizons_hours"],
        lag_hours=config["lag_hours"],
        rolling_windows_hours=config["rolling_windows_hours"],
    )
    print(f"[feature] Feature rows: {len(features)}")

    result = save_features(features, config)
    print(f"[feature] Saved via {result}")
    return result

def main() -> None:
    parser = argparse.ArgumentParser(description="Run AQI feature pipeline")
    parser.add_argument("--past-days", type=int, default=3, help="Days of recent data to fetch")
    args = parser.parse_args()
    run_feature_pipeline(past_days=args.past_days)

if __name__ == "__main__":
    main()
