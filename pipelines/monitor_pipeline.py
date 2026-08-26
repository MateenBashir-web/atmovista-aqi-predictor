
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.monitoring.forecast_log import (
    build_monitoring_summary,
    log_live_forecasts,
    reconcile_with_actuals,
    seed_historical_scores,
)
from src.utils.config import load_config

def run_monitor(seed_history: bool = False) -> dict:
    config = load_config()
    if not config.get("monitoring", {}).get("enabled", True):
        return {"enabled": False}

    result = {"enabled": True}
    if seed_history:
        print("[monitor] Seeding historical forecast-vs-actual scores...")
        result["seed"] = seed_historical_scores(config)
        print(f"[monitor] Seeded {result['seed'].get('seeded', 0)} rows")

    print("[monitor] Logging live forecasts...")
    result["live"] = log_live_forecasts(config)
    print(f"[monitor] Logged {result['live'].get('logged', 0)} forecast rows")

    print("[monitor] Reconciling matured forecasts with actuals...")
    result["reconcile"] = reconcile_with_actuals(config)
    print(
        f"[monitor] Scored={result['reconcile'].get('scored', 0)} "
        f"pending={result['reconcile'].get('pending', 0)}"
    )

    summary = build_monitoring_summary(config)
    result["summary"] = {
        "scored_rows": summary.get("scored_rows"),
        "overall": summary.get("overall"),
        "by_horizon": summary.get("by_horizon"),
    }
    print("[monitor] Summary:", json.dumps(result["summary"], indent=2, default=str))
    return result

def main() -> None:
    parser = argparse.ArgumentParser(description="Forecast vs actual monitoring")
    parser.add_argument(
        "--seed-history",
        action="store_true",
        help="Bootstrap monitor log by scoring recent historical timestamps",
    )
    args = parser.parse_args()
    run_monitor(seed_history=args.seed_history)

if __name__ == "__main__":
    main()
