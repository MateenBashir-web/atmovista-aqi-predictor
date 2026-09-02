
from __future__ import annotations

from pathlib import Path

from fpdf import FPDF, FontFace
from fpdf.enums import TableCellFillMode, XPos, YPos

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "AtmoVista_Internship_Report.pdf"


class ReportPDF(FPDF):
    def header(self) -> None:
        if self.page_no() == 1:
            return
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(100, 100, 100)
        self.cell(0, 6, "AtmoVista - Internship Project Report", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_draw_color(200, 200, 200)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(4)

    def footer(self) -> None:
        self.set_y(-14)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(110, 110, 110)
        self.cell(0, 8, f"Page {self.page_no()}", align="C")


def h1(pdf: ReportPDF, text: str) -> None:
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(18, 40, 70)
    pdf.multi_cell(0, 9, text)
    pdf.ln(2)


def h2(pdf: ReportPDF, text: str) -> None:
    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(25, 55, 95)
    pdf.multi_cell(0, 7, text)
    pdf.ln(1.5)


def h3(pdf: ReportPDF, text: str) -> None:
    pdf.ln(1.5)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(35, 65, 105)
    pdf.multi_cell(0, 6, text)
    pdf.ln(1)


def body(pdf: ReportPDF, text: str) -> None:
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(30, 30, 30)
    pdf.multi_cell(0, 5.2, text)
    pdf.ln(1)


def bullet(pdf: ReportPDF, text: str) -> None:
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(30, 30, 30)
    pdf.set_x(pdf.l_margin + 3)
    pdf.multi_cell(pdf.epw - 3, 5.2, f"- {text}")


def meta_line(pdf: ReportPDF, label: str, value: str) -> None:
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(30, 30, 30)
    pdf.write(5.5, f"{label} ")
    pdf.set_font("Helvetica", "", 10)
    pdf.write(5.5, value)
    pdf.ln(6.5)


def draw_table(pdf: ReportPDF, rows: list[list[str]], col_widths: tuple[float, ...] | None = None) -> None:
    pdf.set_font("Helvetica", size=9)
    pdf.set_text_color(25, 25, 25)
    pdf.set_draw_color(160, 170, 185)
    pdf.set_line_width(0.2)
    headings = FontFace(emphasis="BOLD", color=(20, 35, 55), fill_color=(225, 235, 248))
    kwargs: dict = {
        "first_row_as_headings": True,
        "headings_style": headings,
        "cell_fill_color": (248, 250, 252),
        "cell_fill_mode": TableCellFillMode.ROWS,
        "line_height": 5.2,
        "text_align": "LEFT",
        "padding": (1.5, 2, 1.5, 2),
        "width": pdf.epw,
    }
    if col_widths is not None:
        kwargs["col_widths"] = col_widths
    with pdf.table(**kwargs) as table:
        for row in rows:
            table.row(row)
    pdf.ln(3)


def main() -> None:
    pdf = ReportPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_margins(16, 16, 16)
    pdf.add_page()

    h1(pdf, "AtmoVista - Internship Project Report")
    body(
        pdf,
        "AQI forecasting for Pakistan with MLOps, live deployment, and GitHub Actions automation.",
    )
    meta_line(pdf, "Project title:", "AtmoVista (Pearls AQI Predictor)")
    meta_line(pdf, "Forecast window:", "Next 3 days (+24h, +48h, +72h)")
    meta_line(pdf, "Cities:", "Lahore, Karachi, Islamabad, Peshawar, Quetta")
    meta_line(pdf, "Repository:", "GitHub (with GitHub Actions)")
    meta_line(pdf, "Deployment:", "API on Render, UI on Vercel, features/models on Hopsworks")
    pdf.ln(2)

    h2(pdf, "1. Introduction")
    body(
        pdf,
        "For my internship project I built AtmoVista, a system that forecasts Air Quality Index (AQI) "
        "for five major cities in Pakistan over the next three days. I collected data, engineered "
        "features, trained and compared multiple models, stored everything in Hopsworks, and deployed "
        "a working web app that can be opened live.",
    )
    body(pdf, "The main parts of the project are:")
    for item in [
        "data collection from Open-Meteo",
        "feature engineering and backfill",
        "model training (Ridge, Random Forest, HistGradientBoosting, LSTM)",
        "Hopsworks feature store and model registry",
        "GitHub Actions for hourly features and daily training",
        "FastAPI backend + React frontend (AtmoVista dashboard)",
    ]:
        bullet(pdf, item)
    pdf.ln(1)
    body(
        pdf,
        "I wanted the app to be useful for normal users (current AQI, 3-day outlook, health tips) "
        "and also clear enough for technical review (model scores, SHAP, monitoring).",
    )

    h2(pdf, "2. Problem statement")
    body(
        pdf,
        "Air quality in Pakistan changes a lot between cities and seasons, especially during smog months. "
        "Based on the internship brief, I focused on these requirements:",
    )
    for item in [
        "Forecast AQI for +24h, +48h, and +72h",
        "Keep data updated on a schedule",
        "Explain why the model predicts a certain level (SHAP / XAI)",
        "Show alerts for unhealthy or hazardous air",
        "Use tools that work on free or low-cost hosting",
    ]:
        bullet(pdf, item)
    pdf.ln(1)
    body(
        pdf,
        "AtmoVista covers these through a full pipeline and a dashboard with two modes: "
        "For you (everyday use) and For experts (models, explainability, accuracy).",
    )

    h2(pdf, "3. Objectives completed")
    draw_table(
        pdf,
        [
            ["Objective", "Status"],
            ["Predict AQI for next 3 days", "Done"],
            ["Feature pipeline (fetch to feature store)", "Done"],
            ["Historical backfill for training", "Done"],
            ["Train and evaluate multiple models", "Done"],
            ["Store models in model registry", "Done"],
            ["Automate hourly and daily pipelines", "Done"],
            ["Interactive AtmoVista dashboard", "Done"],
            ["EDA", "Done"],
            ["SHAP explainability", "Done"],
            ["Hazardous AQI alerts", "Done"],
            ["GitHub + Render + Vercel + Hopsworks", "Done"],
        ],
        col_widths=(2.4, 1.2),
    )
    body(
        pdf,
        "The brief suggested Streamlit or Gradio. My mentor allowed FastAPI + React instead, "
        "so I built a custom UI for better presentation marks.",
    )

    h2(pdf, "4. System overview")
    body(pdf, "This is how the deployed system works:")
    for item in [
        "Open-Meteo APIs provide pollutant and weather data",
        "Feature and backfill pipelines engineer hourly features",
        "Features are stored in the Hopsworks Feature Store",
        "Training compares Ridge, Random Forest, HistGradientBoosting, and LSTM",
        "Winning models are registered in the Hopsworks Model Registry",
        "FastAPI loads models/features and serves forecasts",
        "The AtmoVista React dashboard consumes the API",
        "GitHub Actions keeps features and models updated on schedule",
    ]:
        bullet(pdf, item)
    pdf.ln(1)
    h3(pdf, "Main layers")
    draw_table(
        pdf,
        [
            ["Layer", "Responsibility"],
            ["Data", "Open-Meteo air quality and weather"],
            ["Features", "Time, lag, rolling, future-weather features and targets"],
            ["Storage", "Hopsworks Feature Group and Model Registry"],
            ["Training", "Per-horizon model selection"],
            ["Serving", "FastAPI inference API"],
            ["Presentation", "AtmoVista React dashboard"],
            ["Automation", "GitHub Actions hourly and daily jobs"],
        ],
        col_widths=(1.0, 2.6),
    )

    h2(pdf, "5. Technology stack")
    draw_table(
        pdf,
        [
            ["Area", "Choice", "Why I used it"],
            ["Language", "Python", "Required for ML pipelines"],
            ["Classical ML", "Scikit-learn", "Ridge / RF / HistGB"],
            ["Deep learning", "TensorFlow LSTM", "Required advanced model"],
            ["Feature store", "Hopsworks", "Feature Store + Model Registry in brief"],
            ["Orchestration", "GitHub Actions", "Free CI/CD (instead of Airflow)"],
            ["API", "FastAPI", "Serve forecasts to the UI"],
            ["UI", "React + Vite + TypeScript", "Custom frontend (mentor approved)"],
            ["Explainability", "SHAP", "Required XAI; per-horizon signed drivers"],
            ["Deploy", "Render + Vercel", "Host API and frontend"],
        ],
        col_widths=(1.1, 1.4, 1.5),
    )

    h2(pdf, "6. Data collection")
    body(
        pdf,
        "I used the Open-Meteo Air Quality API and Weather API because they are free and do not "
        "need a paid key. The brief mentioned AQICN/OpenWeather as examples; Open-Meteo was enough "
        "for this project.",
    )
    h3(pdf, "Pollutants / AQI")
    for item in ["PM2.5, PM10, CO, NO2, SO2, O3", "US AQI (preferred) / European AQI fallback"]:
        bullet(pdf, item)
    h3(pdf, "Weather")
    for item in [
        "temperature, humidity, precipitation",
        "wind speed / direction",
        "cloud cover, surface pressure",
    ]:
        bullet(pdf, item)
    h3(pdf, "Cities and coordinates")
    draw_table(
        pdf,
        [
            ["City", "Latitude", "Longitude"],
            ["Lahore", "31.5204", "74.3587"],
            ["Karachi", "24.8607", "67.0011"],
            ["Islamabad", "33.6844", "73.0479"],
            ["Peshawar", "34.0151", "71.5249"],
            ["Quetta", "30.1798", "66.9750"],
        ],
        col_widths=(1.4, 1.3, 1.3),
    )
    h3(pdf, "Training scale")
    draw_table(
        pdf,
        [
            ["Item", "Value"],
            ["Backfill window", "365 days"],
            ["Dataset size (EDA)", "43,800 hourly rows"],
            ["Cities covered", "5"],
        ],
        col_widths=(1.6, 2.0),
    )

    h2(pdf, "7. Feature engineering")
    body(pdf, "I implemented features in src/features/engineering.py.")
    draw_table(
        pdf,
        [
            ["Group", "Examples"],
            ["Raw signals", "pollutants, weather, current AQI"],
            ["Time features", "hour, day, day_of_week, month, sin/cos encodings"],
            ["Derived features", "AQI change rate, temp x humidity, wind x PM2.5"],
            ["Lag features", "AQI and PM2.5 lags at 1, 3, 6, 12, 24, 48, 72 hours"],
            ["Rolling stats", "mean/std over 6h, 12h, 24h windows"],
            ["Future weather", "weather at t+24 / t+48 / t+72"],
            ["Targets", "aqi_target_24h, aqi_target_48h, aqi_target_72h"],
        ],
        col_widths=(1.2, 2.8),
    )
    body(pdf, "Design choices:")
    for item in [
        "Separate model per horizon (+24h, +48h, +72h) - better accuracy in my experiments",
        "Controlled noise on future-weather features during training (realistic mode)",
        "Prediction intervals (80%) from validation residuals",
    ]:
        bullet(pdf, item)

    h2(pdf, "8. Exploratory data analysis (EDA)")
    body(pdf, "EDA notebook: notebooks/eda.ipynb. Plots include timeseries, correlation heatmap, seasonality, and city boxplots.")
    body(pdf, "What I found:")
    for item in [
        "Lahore has the highest median AQI and the biggest spikes (smog).",
        "Karachi is the most stable city with the lowest mean AQI in my dataset.",
        "PM2.5 and PM10 correlate most strongly with AQI.",
        "Evening/night and winter months (Nov to Jan) tend to have higher AQI on average.",
        "Each city behaves differently, so error varies by city.",
    ]:
        bullet(pdf, item)
    pdf.ln(1)
    h3(pdf, "City AQI summary (from EDA)")
    draw_table(
        pdf,
        [
            ["City", "Mean", "Std", "Median", "Max"],
            ["Islamabad", "113.0", "30.7", "107.0", "206"],
            ["Karachi", "90.1", "21.8", "85.0", "165"],
            ["Lahore", "153.0", "49.1", "154.0", "364"],
            ["Peshawar", "114.6", "29.0", "111.0", "212"],
            ["Quetta", "86.4", "31.7", "77.0", "332"],
        ],
        col_widths=(1.2, 0.7, 0.7, 0.8, 0.6),
    )
    h3(pdf, "Forecast difficulty by city")
    draw_table(
        pdf,
        [
            ["Difficulty", "Cities"],
            ["Hardest", "Lahore, Quetta"],
            ["More stable", "Karachi, Peshawar"],
        ],
        col_widths=(1.2, 2.4),
    )

    h2(pdf, "9. Training pipeline")
    body(pdf, "Script: pipelines/training_pipeline.py")
    h3(pdf, "Models experimented")
    draw_table(
        pdf,
        [
            ["Model", "Library"],
            ["Ridge Regression", "Scikit-learn"],
            ["Random Forest", "Scikit-learn"],
            ["HistGradientBoosting", "Scikit-learn"],
            ["LSTM", "TensorFlow"],
        ],
        col_widths=(1.8, 1.8),
    )
    h3(pdf, "Evaluation metrics")
    draw_table(
        pdf,
        [
            ["Metric", "Purpose"],
            ["RMSE", "Main selection metric"],
            ["MAE", "Average absolute error"],
            ["R2", "Explained variance"],
            ["Category accuracy", "AQI band match for user-facing quality"],
        ],
        col_widths=(1.4, 2.2),
    )
    body(pdf, "Best model is selected per horizon using validation RMSE.")
    draw_table(
        pdf,
        [
            ["Horizon", "Selected model"],
            ["+24h", "Ridge"],
            ["+48h", "HistGradientBoosting"],
            ["+72h", "Ridge"],
        ],
        col_widths=(1.2, 2.4),
    )
    body(pdf, "Winner label: ridge@24h+hist_gradient_boosting@48h+ridge@72h  |  Trained: 2026-08-11")

    h2(pdf, "10. Results")
    h3(pdf, "10.1 Validation metrics (winner models)")
    draw_table(
        pdf,
        [
            ["Horizon", "Winner", "RMSE", "MAE", "R2", "Category Acc."],
            ["+24h", "Ridge", "21.63", "14.33", "0.716", "72.8%"],
            ["+48h", "HistGB", "26.22", "18.64", "0.583", "59.9%"],
            ["+72h", "Ridge", "28.47", "19.78", "0.508", "61.2%"],
        ],
        col_widths=(0.7, 0.8, 0.7, 0.7, 0.7, 1.0),
    )
    h3(pdf, "10.2 Test metrics (winner models)")
    draw_table(
        pdf,
        [
            ["Horizon", "Winner", "RMSE", "MAE", "R2", "Category Acc."],
            ["+24h", "Ridge", "20.63", "14.77", "0.611", "67.8%"],
            ["+48h", "HistGB", "26.63", "19.26", "0.352", "58.1%"],
            ["+72h", "Ridge", "28.18", "20.90", "0.275", "54.9%"],
        ],
        col_widths=(0.7, 0.8, 0.7, 0.7, 0.7, 1.0),
    )
    h3(pdf, "10.3 My reading of the results")
    for item in [
        "+24h forecasts are the strongest, which is expected.",
        "Error increases at +48h and +72h.",
        "All horizons beat a simple persistence baseline in my evaluation.",
        "Category accuracy matters because users care about bands, not only the exact number.",
    ]:
        bullet(pdf, item)
    pdf.ln(1)
    h3(pdf, "10.4 Live monitoring (forecast vs actual)")
    body(pdf, "Source: artifacts/monitoring/summary.json")
    draw_table(
        pdf,
        [
            ["Scope", "MAE", "RMSE", "R2", "Category Acc.", "Scored rows"],
            ["Overall", "12.33", "19.32", "0.744", "74.8%", "3500"],
            ["+24h", "10.42", "15.84", "0.830", "78.8%", "1170"],
            ["+48h", "13.48", "20.56", "0.709", "72.1%", "1165"],
            ["+72h", "13.10", "21.13", "0.691", "73.4%", "1165"],
        ],
        col_widths=(0.8, 0.7, 0.7, 0.7, 1.0, 0.9),
    )
    h3(pdf, "Per-city live MAE")
    draw_table(
        pdf,
        [
            ["City", "MAE", "Category Acc.", "Scored rows"],
            ["Karachi", "4.68", "97.6%", "700"],
            ["Islamabad", "13.15", "66.7%", "700"],
            ["Peshawar", "12.95", "70.1%", "700"],
            ["Quetta", "14.51", "71.1%", "700"],
            ["Lahore", "16.36", "68.3%", "700"],
        ],
        col_widths=(1.2, 0.8, 1.1, 1.0),
    )
    body(pdf, "Karachi tracks best in live monitoring. Lahore is the hardest of the five cities.")

    h2(pdf, "11. Feature store and model registry (Hopsworks)")
    draw_table(
        pdf,
        [
            ["Item", "Value"],
            ["Feature Group", "aqi_features (v3)"],
            ["Feature contents", "Engineered hourly features + targets for 5 cities"],
            ["Model Registry", "aqi_forecast_model"],
            ["Bundle", "Per-horizon winners synced by hopsworks_sync.py"],
        ],
        col_widths=(1.3, 2.7),
    )
    body(
        pdf,
        "In production (STORAGE_MODE=hopsworks) the API reads features from Hopsworks and caches "
        "them in memory. Training jobs can still use local parquet when needed.",
    )

    h2(pdf, "12. Inference and API")
    body(pdf, "API module: api/main.py")
    draw_table(
        pdf,
        [
            ["Endpoint area", "What it serves"],
            ["Forecast", "Current AQI + 3-day forecast"],
            ["History", "Recent AQI history"],
            ["Weather", "Temperature, humidity, wind, pollutant driver"],
            ["Health tips / exercise", "Practical guidance"],
            ["Alerts", "Hazardous / unhealthy warnings"],
            ["Explain", "Per-horizon SHAP, waterfall, narrative, city compare"],
            ["Leaderboard / ops / monitoring", "Model and pipeline health"],
        ],
        col_widths=(1.6, 2.4),
    )
    body(pdf, "Prediction flow:")
    for item in [
        "Load latest feature row for selected city",
        "Fill future-weather fields from Open-Meteo forecast",
        "Run the horizon-specific winner model",
        "Apply prediction interval",
        "Map AQI to EPA-style category + color",
        "Return JSON to the AtmoVista frontend",
    ]:
        bullet(pdf, item)

    h2(pdf, "13. AtmoVista dashboard (frontend)")
    body(pdf, "Built with React + Vite + TypeScript and deployed on Vercel.")
    h3(pdf, "For you (everyday mode)")
    for item in [
        "Pakistan live map + city rankings",
        "Current AQI gauge with category bands",
        "Weather strip, pollutant breakdown, 3-day outlook with calendar dates",
        "Confidence / peak / improvement insights",
        "Health tips, alerts, exercise advice, smog season panel, city watchlist",
    ]:
        bullet(pdf, item)
    h3(pdf, "For experts (technical mode)")
    for item in [
        "Ops strip (storage mode, model, sync)",
        "Beat-the-baseline panel and pipeline health board",
        "Model leaderboard",
        "XAI: per-horizon SHAP, signed local drivers, waterfall, narrative",
        "Global drivers, city SHAP compare, glossary hover, pollutant link",
        "Live accuracy table (forecast vs actual)",
    ]:
        bullet(pdf, item)

    h2(pdf, "14. Alerts and health guidance")
    draw_table(
        pdf,
        [
            ["Feature", "Behavior"],
            ["Alerts", "Shown for unhealthy/hazardous current or forecast AQI with date"],
            ["Health tips", "Category-based guidance for masking, exposure, sensitive groups"],
            ["Exercise advice", "Decision card for outdoor exercise based on near-term AQI"],
        ],
        col_widths=(1.2, 2.8),
    )

    h2(pdf, "15. Explainability (SHAP)")
    body(
        pdf,
        "Implemented in src/inference/explain.py and shown in the expert dashboard "
        "(/aqi/explain, plus compare/global helpers).",
    )
    draw_table(
        pdf,
        [
            ["View", "Purpose"],
            ["Per-horizon tabs", "Separate explanations for +24h, +48h, and +72h winners"],
            ["City-level importance", "Mean |SHAP| over recent city rows"],
            ["Signed local explanation", "Latest-hour SHAP with direction (raises / lowers AQI)"],
            ["Waterfall", "Step path from baseline value to predicted AQI"],
            ["Plain-language narrative", "Short sentence summarizing the top drivers"],
            ["Global training drivers", "Surfaces artifacts/shap_summary.json from training"],
            ["City compare", "Top SHAP drivers across Pakistan cities"],
            ["Feature glossary", "Hover tooltips for lag / weather / pollutant names"],
            ["Pollutant link", "Whether live chemistry and SHAP agree on signal family"],
        ],
        col_widths=(1.5, 2.5),
    )
    body(
        pdf,
        "Common drivers in my models: recent AQI/PM lags, rolling AQI stats, and weather features.",
    )

    h2(pdf, "16. Automation / CI-CD (GitHub Actions)")
    body(pdf, "The repository is on GitHub. Scheduled workflows keep the system updated.")
    draw_table(
        pdf,
        [
            ["Workflow", "Schedule", "What it does"],
            ["feature-hourly.yml", "Hourly", "Refresh features + reconcile monitoring"],
            ["training-daily.yml", "Daily", "Retrain models + sync to Hopsworks"],
            ["monitor-daily.yml", "Daily", "Maintain scored forecast-vs-actual history"],
        ],
        col_widths=(1.4, 0.8, 1.8),
    )
    body(pdf, "Repository secrets used by Actions: HOPSWORKS_API_KEY, HOPSWORKS_PROJECT, HOPSWORKS_HOST (optional).")

    h2(pdf, "17. Deployment")
    draw_table(
        pdf,
        [
            ["Service", "Platform", "Status"],
            ["AtmoVista frontend", "Vercel", "Deployed"],
            ["FastAPI backend", "Render (Standard for reliable demo)", "Deployed"],
            ["Feature store / models", "Hopsworks", "Live source of truth"],
        ],
        col_widths=(1.4, 1.4, 1.2),
    )
    body(pdf, "Production configuration:")
    for item in [
        "Render uses STORAGE_MODE=hopsworks and Hopsworks credentials",
        "Vercel uses VITE_API_URL pointing to the Render API",
        "CORS allows the Vercel frontend origin",
    ]:
        bullet(pdf, item)

    h2(pdf, "18. Extra features (beyond basic brief)")
    draw_table(
        pdf,
        [
            ["Feature", "Reason"],
            ["5 Pakistan cities", "More useful than single-city demo"],
            ["Two UI modes", "Everyday users + technical review"],
            ["Pollutant breakdown", "Context around the AQI number"],
            ["Signed SHAP + waterfall", "Clearer explainability"],
            ["Confidence bands", "Show uncertainty"],
            ["Smog season + exercise cards", "Practical for users"],
            ["Live monitoring", "Compare forecasts to actual AQI"],
            ["Beat-persistence baseline", "Show the model adds value"],
        ],
        col_widths=(1.5, 2.5),
    )

    h2(pdf, "19. Limitations")
    for item in [
        "Open-Meteo AQI is model-based, not always the same as a local sensor.",
        "+48h and +72h errors are naturally higher.",
        "Hopsworks free usage and hosting costs (Render Standard) need to be watched.",
        "LSTM was trained but classical models won on most horizons for this data.",
    ]:
        bullet(pdf, item)

    h2(pdf, "20. Future work")
    for item in [
        "Fuse station-level AQI (where available) for calibration",
        "Probabilistic category forecasts (not only point AQI)",
        "City-specific specialist models",
        "Push notifications for hazardous alerts",
        "Longer live monitoring window for stronger trust metrics",
        "Stronger uptime monitoring for the public demo",
    ]:
        bullet(pdf, item)

    h2(pdf, "21. Conclusion")
    body(
        pdf,
        "I completed the internship project as a full AQI forecasting pipeline: data, features, "
        "training, Hopsworks, automation, explainability, alerts, and a deployed dashboard. "
        "The app is on GitHub and runs live on Render and Vercel.",
    )
    body(pdf, "Main results:")
    for item in [
        "Best results at +24h (validation R2 about 0.72, category accuracy about 73%)",
        "Live monitoring on 3500 scored rows: overall MAE about 12.3, category accuracy about 75%",
    ]:
        bullet(pdf, item)
    pdf.ln(1)
    body(
        pdf,
        "I think this is good enough for short-term air quality planning in the cities I covered.",
    )

    h2(pdf, "22. Appendix - important files")
    draw_table(
        pdf,
        [
            ["Path", "Role"],
            ["pipelines/feature_pipeline.py", "Hourly feature refresh"],
            ["pipelines/backfill.py", "Historical training data"],
            ["pipelines/training_pipeline.py", "Model training and selection"],
            ["pipelines/hopsworks_sync.py", "Feature and model sync"],
            ["pipelines/monitor_pipeline.py", "Forecast vs actual logging"],
            ["api/main.py", "FastAPI serving"],
            ["frontend/src/App.tsx", "AtmoVista dashboard"],
            ["artifacts/model_leaderboard.json", "Training results"],
            ["notebooks/eda.ipynb", "EDA"],
            [".github/workflows/", "CI/CD automation"],
            ["docs/AtmoVista_Internship_Report.pdf", "This report"],
        ],
        col_widths=(2.0, 2.0),
    )

    pdf.ln(2)
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(90, 90, 90)
    pdf.multi_cell(0, 5, "AtmoVista / Pearls AQI Predictor - internship submission.")

    pdf.output(str(OUT))
    print(f"Wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
