
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.openmeteo import fetch_city_raw
from src.features.engineering import engineer_features
from src.utils.config import load_config
from src.utils.storage import save_features

def _chunk_ranges(start, end, chunk_days: int = 30):
    cursor = start
    while cursor <= end:
        chunk_end = min(cursor + timedelta(days=chunk_days - 1), end)
        yield cursor, chunk_end
        cursor = chunk_end + timedelta(days=1)

def run_backfill(days: int | None = None, chunk_days: int = 30) -> dict:
    config = load_config()
    days = days or int(config.get("backfill_days", 120))
    end = datetime.now(timezone.utc).date() - timedelta(days=1)
    start = end - timedelta(days=days - 1)

    all_features = []
    for city in config["cities"]:
        print(f"[backfill] {city['name']}: {start} -> {end}")
        city_frames = []
        for c_start, c_end in _chunk_ranges(start, end, chunk_days=chunk_days):
            print(f"  chunk {c_start} -> {c_end}")
            raw = fetch_city_raw(city, start=c_start, end=c_end)
            if raw.empty:
                print("  (empty chunk, skipping)")
                continue
            city_frames.append(raw)

        if not city_frames:
            print(f"[backfill] No data for {city['name']}")
            continue

        import pandas as pd

        raw_city = pd.concat(city_frames, ignore_index=True)
        raw_city = raw_city.drop_duplicates(subset=["event_time"]).sort_values("event_time")
        feats = engineer_features(
            raw_city,
            horizons_hours=config["horizons_hours"],
            lag_hours=config["lag_hours"],
            rolling_windows_hours=config["rolling_windows_hours"],
        )
        all_features.append(feats)
        print(f"[backfill] {city['name']} feature rows: {len(feats)}")

    if not all_features:
        raise RuntimeError("Backfill produced no features")

    import pandas as pd

    features = pd.concat(all_features, ignore_index=True)
    from src.utils.storage import local_feature_path, resolve_storage_mode

    mode = resolve_storage_mode(config)
    if mode == "local":
        path = local_feature_path(config)
        features = features.drop_duplicates(subset=["city", "event_time"], keep="last")
        features = features.sort_values(["city", "event_time"]).reset_index(drop=True)
        features.to_parquet(path, index=False)
        result = {"mode": "local", "path": str(path), "rows": len(features)}
    else:
        result = save_features(features, config)

    print(f"[backfill] Done: {result}")
    return result

def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill historical AQI features")
    parser.add_argument("--days", type=int, default=None, help="Number of past days to backfill")
    parser.add_argument("--chunk-days", type=int, default=30, help="API request chunk size")
    args = parser.parse_args()
    run_backfill(days=args.days, chunk_days=args.chunk_days)

if __name__ == "__main__":
    main()
