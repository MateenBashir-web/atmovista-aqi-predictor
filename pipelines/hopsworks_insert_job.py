
from __future__ import annotations

import os

import hopsworks
import pandas as pd

def main() -> None:
    fg_version = int(os.environ.get("HOPSWORKS_FG_VERSION", "3"))
    project = hopsworks.login()
    fs = project.get_feature_store()
    ds_api = project.get_dataset_api()

    local_copy = "/tmp/aqi_features.parquet"
    remote = "Resources/aqi_data/aqi_features.parquet"
    print(f"Downloading {remote} -> {local_copy}")
    ds_api.download(remote, local_copy, overwrite=True)

    df = pd.read_parquet(local_copy)
    df["event_time"] = pd.to_datetime(df["event_time"], utc=True)
    print(f"Loaded rows={len(df)} cols={len(df.columns)} cities={sorted(df['city'].unique())}")

    fg = fs.get_or_create_feature_group(
        name="aqi_features",
        version=fg_version,
        description="Hourly AQI features — 1-year backfill, per-horizon targets, future weather",
        primary_key=["city", "event_time"],
        event_time="event_time",
        online_enabled=True,
        time_travel_format="DELTA",
    )
    print(f"Inserting into {fg.name} v{fg.version}")
    fg.insert(df, write_options={"wait_for_job": True})
    print("INSERT COMPLETE")

if __name__ == "__main__":
    main()
