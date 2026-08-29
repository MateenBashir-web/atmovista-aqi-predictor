from __future__ import annotations

import pandas as pd


def latest_observed_row(city_df: pd.DataFrame) -> pd.Series:
    """Latest hourly row that is not in the future (Open-Meteo includes forecast hours for today)."""
    if city_df.empty:
        raise ValueError("No rows available")
    work = city_df.sort_values("event_time")
    times = pd.to_datetime(work["event_time"], utc=True)
    now = pd.Timestamp.now(tz="UTC").floor("h")
    observed = work[times <= now]
    if observed.empty:
        return work.iloc[-1]
    return observed.iloc[-1]
