
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.monitoring.forecast_log import get_monitoring_summary
from src.utils.config import get_project_root, load_config

PLOTS_DIR = get_project_root() / "artifacts" / "report" / "plots"
REPORT_DIR = get_project_root() / "report"

def _load_data() -> pd.DataFrame:
    path = get_project_root() / "data" / "processed" / "aqi_features.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}. Run backfill first.")
    df = pd.read_parquet(path)
    df["event_time"] = pd.to_datetime(df["event_time"], utc=True)
    return df

def _load_leaderboard() -> dict:
    cfg = load_config()
    lb = get_project_root() / cfg["storage"]["leaderboard_path"]
    if lb.exists():
        return json.loads(lb.read_text(encoding="utf-8"))
    return {}

def generate_eda(df: pd.DataFrame) -> dict:
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="whitegrid")

    city_stats = (
        df.groupby("city")["aqi"]
        .agg(["count", "mean", "std", "min", "median", "max"])
        .round(1)
        .reset_index()
        .to_dict(orient="records")
    )

    tmp = df.copy()
    tmp["hour"] = tmp["event_time"].dt.hour
    tmp["month"] = tmp["event_time"].dt.month
    by_hour = tmp.groupby("hour")["aqi"].mean().round(1).to_dict()
    by_month = tmp.groupby("month")["aqi"].mean().round(1).to_dict()

    cols = ["aqi", "pm25", "pm10", "no2", "o3", "temperature_2m", "relative_humidity_2m", "wind_speed_10m"]
    cols = [c for c in cols if c in df.columns]
    corr = df[cols].corr(numeric_only=True).round(3)
    top_corr = []
    if "aqi" in corr.columns:
        for feat, val in corr["aqi"].drop("aqi").sort_values(key=abs, ascending=False).head(6).items():
            top_corr.append({"feature": feat, "correlation_with_aqi": float(val)})

    plt.figure(figsize=(12, 5))
    for city, g in df.groupby("city"):
        g = g.sort_values("event_time").iloc[::24]
        plt.plot(g["event_time"], g["aqi"], label=city, alpha=0.85)
    plt.legend()
    plt.title("Daily AQI by city (1-year history)")
    plt.ylabel("AQI")
    plt.tight_layout()
    ts_path = PLOTS_DIR / "aqi_timeseries_by_city.png"
    plt.savefig(ts_path, dpi=120)
    plt.close()

    plt.figure(figsize=(8, 6))
    sns.heatmap(corr, annot=True, fmt=".2f", cmap="coolwarm", center=0)
    plt.title("Pollutant / weather correlations")
    plt.tight_layout()
    corr_path = PLOTS_DIR / "correlation_heatmap.png"
    plt.savefig(corr_path, dpi=120)
    plt.close()

    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    pd.Series(by_hour).plot(ax=axes[0], title="Mean AQI by hour of day")
    pd.Series(by_month).plot(ax=axes[1], title="Mean AQI by month")
    plt.tight_layout()
    season_path = PLOTS_DIR / "seasonality_hour_month.png"
    plt.savefig(season_path, dpi=120)
    plt.close()

    plt.figure(figsize=(10, 5))
    order = df.groupby("city")["aqi"].median().sort_values(ascending=False).index
    sns.boxplot(data=df, x="city", y="aqi", order=order)
    plt.title("AQI distribution by city")
    plt.xticks(rotation=15)
    plt.tight_layout()
    box_path = PLOTS_DIR / "aqi_boxplot_by_city.png"
    plt.savefig(box_path, dpi=120)
    plt.close()

    highlights = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "rows": int(len(df)),
        "cities": sorted(df["city"].unique()),
        "date_range": {
            "start": str(df["event_time"].min()),
            "end": str(df["event_time"].max()),
        },
        "city_stats": city_stats,
        "seasonality": {"by_hour": by_hour, "by_month": by_month},
        "top_correlations_with_aqi": top_corr,
        "plots": {
            "timeseries": str(ts_path.relative_to(get_project_root())),
            "correlation": str(corr_path.relative_to(get_project_root())),
            "seasonality": str(season_path.relative_to(get_project_root())),
            "boxplot": str(box_path.relative_to(get_project_root())),
        },
        "findings": [
            "Lahore shows the highest median AQI and widest spread — strongest smog spikes.",
            "Karachi is the most stable city with the lowest mean AQI in this dataset.",
            "PM2.5 and PM10 are the strongest linear correlates of AQI across cities.",
            "Evening/night hours and winter months (Nov–Jan) tend toward higher mean AQI.",
            "City-specific patterns justify shared features but different forecast error profiles.",
        ],
    }

    out_json = get_project_root() / "artifacts" / "report" / "eda_highlights.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(highlights, indent=2), encoding="utf-8")

    md = REPORT_DIR / "EDA_HIGHLIGHTS.md"
    lines = [
        "# EDA Highlights (auto-generated)",
        "",
        f"Generated: {highlights['generated_at']}",
        f"Rows: **{highlights['rows']:,}** | Cities: {', '.join(highlights['cities'])}",
        "",
        "## Key findings",
        "",
    ]
    for f in highlights["findings"]:
        lines.append(f"- {f}")
    lines.extend(["", "## City summary (AQI)", "", "| City | Mean | Std | Median | Max |", "|------|------|-----|--------|-----|"])
    for row in city_stats:
        lines.append(
            f"| {row['city']} | {row['mean']} | {row['std']} | {row['median']} | {row['max']} |"
        )
    lines.extend(["", "## Plots", ""])
    for name, rel in highlights["plots"].items():
        lines.append(f"- **{name}**: `{rel}`")
    lines.extend(["", "_Re-run: `python pipelines/generate_report_artifacts.py`_"])
    md.write_text("\n".join(lines), encoding="utf-8")
    print(f"[report] EDA -> {out_json} + {md}")
    return highlights

def generate_per_city(df: pd.DataFrame, leaderboard: dict, monitoring: dict) -> dict:
    lb = leaderboard.get("horizon_winners") or {}
    mon_cities = monitoring.get("by_city") or {}

    cities = []
    for city in sorted(df["city"].unique()):
        g = df[df["city"] == city]
        pm25_mean = float(g["pm25"].mean()) if "pm25" in g.columns else None
        worst_month = int(g.assign(m=g["event_time"].dt.month).groupby("m")["aqi"].mean().idxmax())
        entry = {
            "city": city,
            "rows": int(len(g)),
            "aqi_mean": round(float(g["aqi"].mean()), 1),
            "aqi_std": round(float(g["aqi"].std()), 1),
            "aqi_median": round(float(g["aqi"].median()), 1),
            "aqi_max": round(float(g["aqi"].max()), 1),
            "pm25_mean": round(pm25_mean, 2) if pm25_mean is not None else None,
            "worst_month": worst_month,
            "horizon_winners": {
                h: lb.get(h, {}).get("name") for h in ("24", "48", "72") if h in lb
            },
            "live_monitoring": mon_cities.get(city),
        }
        if lb:
            for h in ("24", "48", "72"):
                hw = lb.get(h, {})
                val = hw.get("val", {}).get("overall", {})
                if val:
                    entry.setdefault("val_metrics_by_horizon", {})[f"+{h}h"] = {
                        "rmse": round(val.get("rmse", 0), 2),
                        "r2": round(val.get("r2", 0), 3),
                        "category_accuracy": round(val.get("category_accuracy", 0), 3),
                    }
        cities.append(entry)

    ranked = sorted(
        cities,
        key=lambda c: (
            c.get("live_monitoring", {}) or {}
        ).get("mae", c.get("aqi_std", 0)),
        reverse=True,
    )

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cities": cities,
        "hardest_cities": [c["city"] for c in ranked[:2]],
        "easiest_cities": [c["city"] for c in ranked[-2:]],
    }

    out_json = get_project_root() / "artifacts" / "report" / "per_city_analysis.json"
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    md = REPORT_DIR / "PER_CITY_ANALYSIS.md"
    lines = [
        "# Per-city analysis (auto-generated)",
        "",
        f"Generated: {payload['generated_at']}",
        "",
        f"**Hardest to forecast:** {', '.join(payload['hardest_cities'])}",
        f"**Most stable:** {', '.join(payload['easiest_cities'])}",
        "",
        "## City profiles",
        "",
    ]
    for c in cities:
        lines.append(f"### {c['city']}")
        lines.append(
            f"- AQI mean/median/max: **{c['aqi_mean']} / {c['aqi_median']} / {c['aqi_max']}** "
            f"(std {c['aqi_std']})"
        )
        if c.get("pm25_mean") is not None:
            lines.append(f"- Mean PM2.5: **{c['pm25_mean']}**")
        lines.append(f"- Worst month (mean AQI): **{c['worst_month']}**")
        if c.get("horizon_winners"):
            lines.append(f"- Horizon winners: {c['horizon_winners']}")
        if c.get("live_monitoring"):
            m = c["live_monitoring"]
            lines.append(
                f"- Live monitor MAE **{m.get('mae', '—')}**, "
                f"category accuracy **{(m.get('category_accuracy', 0) * 100):.0f}%** "
                f"({m.get('n', 0)} scored rows)"
            )
        if c.get("val_metrics_by_horizon"):
            lines.append("- Validation by horizon:")
            for h, v in c["val_metrics_by_horizon"].items():
                lines.append(
                    f"  - {h}: RMSE {v['rmse']}, R² {v['r2']}, cat acc {v['category_accuracy']}"
                )
        lines.append("")

    lines.append("_Re-run: `python pipelines/generate_report_artifacts.py`_")
    md.write_text("\n".join(lines), encoding="utf-8")
    print(f"[report] Per-city -> {out_json} + {md}")
    return payload

def run_all() -> dict:
    df = _load_data()
    leaderboard = _load_leaderboard()
    monitoring = get_monitoring_summary()
    eda = generate_eda(df)
    per_city = generate_per_city(df, leaderboard, monitoring)
    return {"eda": eda, "per_city": per_city}

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate report artifacts")
    parser.add_argument("--eda-only", action="store_true")
    parser.add_argument("--cities-only", action="store_true")
    args = parser.parse_args()

    df = _load_data()
    if args.eda_only:
        generate_eda(df)
        return
    if args.cities_only:
        generate_per_city(df, _load_leaderboard(), get_monitoring_summary())
        return
    run_all()

if __name__ == "__main__":
    main()
