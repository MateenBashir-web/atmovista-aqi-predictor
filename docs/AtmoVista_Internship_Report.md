# AtmoVista — Internship Project Report

**Project title:** AtmoVista (Pearls AQI Predictor)  
**Theme:** AQI forecasting for Pakistan with MLOps  
**Forecast window:** Next 3 days (+24h, +48h, +72h)  
**Cities:** Lahore, Karachi, Islamabad, Peshawar, Quetta  
**Repository:** GitHub (with GitHub Actions)  
**Deployment:** FastAPI on Render, React UI on Vercel, features/models on Hopsworks

---

## 1. Introduction

For my internship project I built **AtmoVista**, a system that forecasts Air Quality Index (AQI) for five major cities in Pakistan over the next three days. I collected data, engineered features, trained and compared multiple models, stored everything in Hopsworks, and deployed a working web app that mentors and users can open live.

The main parts of the project are:

- data collection from Open-Meteo
- feature engineering and backfill
- model training (Ridge, Random Forest, HistGradientBoosting, LSTM)
- Hopsworks feature store and model registry
- GitHub Actions for hourly features and daily training
- FastAPI backend + React frontend (AtmoVista dashboard)

I wanted the app to be useful for normal users (current AQI, 3-day outlook, health tips) and also clear enough for technical review (model scores, SHAP, monitoring).

---

## 2. Problem statement

Air quality in Pakistan changes a lot between cities and seasons, especially during smog months. Based on the internship brief, I focused on these requirements:

1. Forecast AQI for +24h, +48h, and +72h
2. Keep data updated on a schedule
3. Explain why the model predicts a certain level (SHAP / XAI)
4. Show alerts for unhealthy or hazardous air
5. Use tools that work on free or low-cost hosting

AtmoVista covers these through a full pipeline and a dashboard with two modes: **For you** (everyday use) and **For experts** (models, explainability, accuracy).

---

## 3. Objectives completed

| Objective | Status |
|---|---|
| Predict AQI for next 3 days | Done |
| Feature pipeline (fetch → features → feature store) | Done |
| Historical backfill for training | Done |
| Train and evaluate multiple models | Done |
| Store models in model registry | Done |
| Automate hourly and daily pipelines (GitHub Actions) | Done |
| Interactive dashboard with forecasts | Done (AtmoVista React UI) |
| EDA | Done |
| SHAP explainability | Done |
| Hazardous AQI alerts | Done |
| AQI Copilot chat (Groq + fallback) | Done |
| GitHub repository + deployment | Done (GitHub, Render, Vercel, Hopsworks) |

The brief suggested Streamlit or Gradio. My mentor allowed FastAPI + React instead, so I built a custom UI for better presentation marks.

---

## 4. System overview

This is how the deployed system works:

1. Open-Meteo provides air quality and weather data
2. Backfill and feature pipelines create hourly features
3. Features go into the Hopsworks Feature Store
4. Training compares Ridge, Random Forest, HistGradientBoosting, and LSTM
5. Best models per horizon are saved to the Hopsworks Model Registry
6. FastAPI loads models/features and returns forecasts
7. The React dashboard calls the API
8. GitHub Actions refresh features and retrain on schedule

### Main layers

| Layer | Responsibility |
|---|---|
| Data | Open-Meteo air quality and weather |
| Features | Time, lag, rolling, future-weather features and targets |
| Storage | Hopsworks Feature Group and Model Registry |
| Training | Per-horizon model selection |
| Serving | FastAPI inference API |
| Presentation | AtmoVista React dashboard |
| Automation | GitHub Actions hourly and daily jobs |

---

## 5. Technology stack

| Area | Choice | Why I used it |
|---|---|---|
| Language | Python | Required for ML pipelines |
| Classical ML | Scikit-learn | Ridge / RF / HistGB |
| Deep learning | TensorFlow LSTM | Required advanced model |
| Feature store | Hopsworks | Feature Store + Model Registry in brief |
| Orchestration | GitHub Actions | Free CI/CD (instead of Airflow) |
| API | FastAPI | Serve forecasts to the UI |
| UI | React + Vite + TypeScript | Custom frontend (mentor approved) |
| Explainability | SHAP | Required XAI; per-horizon signed drivers |
| Deploy | Render + Vercel | Host API and frontend |

---

## 6. Data collection

### Source

I used the **Open-Meteo Air Quality API** and **Weather API** because they are free and do not need a paid key. The brief mentioned AQICN/OpenWeather as examples; Open-Meteo was enough for this project.

### Variables used

**Pollutants / AQI**

- PM2.5, PM10, CO, NO2, SO2, O3
- US AQI (preferred) / European AQI fallback

**Weather**

- temperature, humidity, precipitation
- wind speed / direction
- cloud cover, surface pressure

### Cities and coordinates

| City | Latitude | Longitude |
|---|---|---|
| Lahore | 31.5204 | 74.3587 |
| Karachi | 24.8607 | 67.0011 |
| Islamabad | 33.6844 | 73.0479 |
| Peshawar | 34.0151 | 71.5249 |
| Quetta | 30.1798 | 66.9750 |

### Training scale

| Item | Value |
|---|---|
| Backfill window | 365 days |
| Dataset size (EDA) | 43,800 hourly rows |
| Cities covered | 5 |

---

## 7. Feature engineering

I implemented features in `src/features/engineering.py`.

### Feature groups

| Group | Examples |
|---|---|
| Raw signals | pollutants, weather, current AQI |
| Time features | hour, day, day_of_week, month, sin/cos encodings |
| Derived features | AQI change rate, temp × humidity, wind × PM2.5 |
| Lag features | AQI and PM2.5 lags at 1, 3, 6, 12, 24, 48, 72 hours |
| Rolling stats | mean/std over 6h, 12h, 24h windows |
| Future weather | weather at t+24 / t+48 / t+72 |
| Targets | aqi_target_24h, aqi_target_48h, aqi_target_72h |

### Design choices

- Separate model per horizon (+24h, +48h, +72h) instead of one multi-output model — this gave better accuracy in my experiments
- Added controlled noise to future-weather features during training (realistic mode)
- Prediction intervals (80%) from validation residuals

---

## 8. Exploratory data analysis (EDA)

**Notebook:** `notebooks/eda.ipynb`  
**Plots:** timeseries, correlation heatmap, seasonality, city boxplots

### What I found

1. Lahore has the highest median AQI and the biggest spikes (smog).
2. Karachi is the most stable city with the lowest mean AQI in my dataset.
3. PM2.5 and PM10 correlate most strongly with AQI.
4. Evening/night and winter months (Nov–Jan) tend to have higher AQI on average.
5. Each city behaves differently, so shared features still make sense but error varies by city.

### City AQI summary (from EDA)

| City | Mean | Std | Median | Max |
|---|---|---|---|---|
| Islamabad | 113.0 | 30.7 | 107.0 | 206 |
| Karachi | 90.1 | 21.8 | 85.0 | 165 |
| Lahore | 153.0 | 49.1 | 154.0 | 364 |
| Peshawar | 114.6 | 29.0 | 111.0 | 212 |
| Quetta | 86.4 | 31.7 | 77.0 | 332 |

### Forecast difficulty by city

| Difficulty | Cities |
|---|---|
| Hardest | Lahore, Quetta |
| More stable | Karachi, Peshawar |

---

## 9. Training pipeline

**Script:** `pipelines/training_pipeline.py`

### Models I trained

| Model | Library |
|---|---|
| Ridge Regression | Scikit-learn |
| Random Forest | Scikit-learn |
| HistGradientBoosting | Scikit-learn |
| LSTM | TensorFlow |

### Metrics used

| Metric | Purpose |
|---|---|
| RMSE | Main metric for picking winners |
| MAE | Average absolute error |
| R² | Explained variance |
| Category accuracy | How often the AQI band (Good, Unhealthy, etc.) is correct |

### Winners (validation RMSE)

| Horizon | Model |
|---|---|
| +24h | Ridge |
| +48h | HistGradientBoosting |
| +72h | Ridge |

**Combined label:** `ridge@24h+hist_gradient_boosting@48h+ridge@72h`  
**Last training run:** 2026-08-11

---

## 10. Results

### 10.1 Validation metrics (winners)

| Horizon | Winner | RMSE | MAE | R² | Category Acc. |
|---|---|---|---|---|---|
| +24h | Ridge | 21.63 | 14.33 | 0.716 | 72.8% |
| +48h | HistGB | 26.22 | 18.64 | 0.583 | 59.9% |
| +72h | Ridge | 28.47 | 19.78 | 0.508 | 61.2% |

### 10.2 Test metrics (winners)

| Horizon | Winner | RMSE | MAE | R² | Category Acc. |
|---|---|---|---|---|---|
| +24h | Ridge | 20.63 | 14.77 | 0.611 | 67.8% |
| +48h | HistGB | 26.63 | 19.26 | 0.352 | 58.1% |
| +72h | Ridge | 28.18 | 20.90 | 0.275 | 54.9% |

### 10.3 My reading of the results

- +24h forecasts are the strongest, which is expected.
- Error increases at +48h and +72h.
- All horizons beat a simple persistence baseline in my evaluation.
- Category accuracy matters because users care about bands (Good / Unhealthy / Hazardous), not only the exact number.

### 10.4 Live monitoring (forecast vs actual)

From `artifacts/monitoring/summary.json`:

| Scope | MAE | RMSE | R² | Category Acc. | Scored rows |
|---|---|---|---|---|---|
| Overall | 12.33 | 19.32 | 0.744 | 74.8% | 3500 |
| +24h | 10.42 | 15.84 | 0.830 | 78.8% | 1170 |
| +48h | 13.48 | 20.56 | 0.709 | 72.1% | 1165 |
| +72h | 13.10 | 21.13 | 0.691 | 73.4% | 1165 |

### Per-city live MAE

| City | MAE | Category Acc. | Scored rows |
|---|---|---|---|
| Karachi | 4.68 | 97.6% | 700 |
| Islamabad | 13.15 | 66.7% | 700 |
| Peshawar | 12.95 | 70.1% | 700 |
| Quetta | 14.51 | 71.1% | 700 |
| Lahore | 16.36 | 68.3% | 700 |

Karachi tracks best in live monitoring. Lahore is the hardest of the five cities.

---

## 11. Feature store and model registry (Hopsworks)

| Item | Value |
|---|---|
| Feature Group | aqi_features (v3) |
| Contents | Hourly features + targets for 5 cities |
| Model Registry | aqi_forecast_model |
| Sync script | `pipelines/hopsworks_sync.py` |

In production (`STORAGE_MODE=hopsworks`) the API reads features from Hopsworks and caches them in memory. Training jobs can still use local parquet when needed.

---

## 12. Inference and API

**File:** `api/main.py`

### What the API provides

| Area | Description |
|---|---|
| Forecast | Current AQI + 3-day forecast |
| History | Recent AQI history |
| Weather | Temperature, humidity, wind, pollutants |
| Health tips / exercise | User guidance |
| Alerts | Unhealthy / hazardous warnings |
| Copilot | Floating chat over live city data (Groq + fallback) |
| Explain | Per-horizon SHAP, waterfall, narrative, city compare |
| Leaderboard / ops / monitoring | Model and pipeline status |

### Prediction steps

1. Load the latest feature row for the city
2. Fill future-weather fields from Open-Meteo
3. Run the winner model for that horizon
4. Add prediction interval
5. Map AQI to category and color
6. Return JSON to the frontend

---

## 13. AtmoVista dashboard

Built with React + Vite + TypeScript, hosted on Vercel.

### For you

- Pakistan map and city rankings
- Current AQI gauge
- Weather and pollutant breakdown
- 3-day outlook with dates
- Health tips, alerts, exercise advice
- Smog season panel and city watchlist
- Floating AQI Copilot (bottom-left chat)

### For experts

- Ops strip (storage, model, last sync)
- Baseline comparison and pipeline health
- Model leaderboard
- SHAP (+24h / +48h / +72h), signed drivers, waterfall, narrative
- Global training drivers, city compare, feature glossary
- Live accuracy (forecast vs actual)

### Other UI features

- Dark / light theme
- Shareable forecast PNG export
- Pakistan timezone on dates and horizons

---

## 14. Alerts, health guidance, and copilot

| Feature | What it does |
|---|---|
| Alerts | Warn when current or forecast AQI is unhealthy or hazardous |
| Health tips | Advice by AQI category (masking, windows, sensitive groups) |
| Exercise advice | Suggests whether outdoor exercise is reasonable |
| AQI Copilot | Chat helper for the selected city; uses live forecast/weather/tips |

I added the copilot so people can ask simple questions (exercise, next 24 hours, what to do now) without digging through every panel. It is a floating button on the bottom-left, like most websites. Backend endpoint: `POST /insights/copilot`.

For the LLM I used **Groq** (free tier, model `openai/gpt-oss-20b`). The key stays on the Render API only. If Groq is down or the key is missing, the same endpoint falls back to rule-based answers from AtmoVista data so the chat still works.

---

## 15. Explainability (SHAP)

**Code:** `src/inference/explain.py`  
**UI:** Experts mode, `/aqi/explain`

| View | Purpose |
|---|---|
| Per-horizon tabs | SHAP for +24h, +48h, +72h models |
| City-level importance | Mean \|SHAP\| over recent rows |
| Signed local SHAP | Latest hour — ↑ raises AQI, ↓ lowers |
| Waterfall | Baseline → prediction steps |
| Narrative | Short summary of top drivers |
| Global drivers | From `artifacts/shap_summary.json` |
| City compare | Top drivers across cities |
| Glossary | Tooltips on feature names |
| Pollutant link | Compare SHAP with live pollutant readings |

Common drivers in my models: recent AQI/PM lags, rolling AQI stats, and weather features.

---

## 16. Automation (GitHub Actions)

| Workflow | Schedule | Task |
|---|---|---|
| feature-hourly.yml | Hourly | Refresh features + monitoring |
| training-daily.yml | Daily | Retrain + sync to Hopsworks |
| monitor-daily.yml | Daily | Update forecast vs actual log |

Secrets: `HOPSWORKS_API_KEY`, `HOPSWORKS_PROJECT`, `HOPSWORKS_HOST` (optional).

---

## 17. Deployment

| Service | Platform | Status |
|---|---|---|
| AtmoVista UI | Vercel | Live |
| FastAPI API | Render (Standard plan for stable demos) | Live |
| Features / models | Hopsworks | Production source |

- Render: `STORAGE_MODE=hopsworks`, Hopsworks credentials in env
- Vercel: `VITE_API_URL` points to Render API
- CORS allows the Vercel domain

**Live links:** https://atmovista.vercel.app · API health on Render

---

## 18. Extra features (beyond basic brief)

| Feature | Reason |
|---|---|
| 5 Pakistan cities | More useful than single-city demo |
| Two UI modes | Everyday users + technical review |
| Pollutant breakdown | Context around the AQI number |
| Signed SHAP + waterfall | Clearer explainability |
| Confidence bands | Show uncertainty |
| Smog season + exercise cards | Practical for users |
| AQI Copilot (Groq + fallback) | Quick Q&A from live city data |
| Live monitoring | Compare forecasts to what actually happened |
| Beat-persistence baseline | Show the model adds value |

---

## 19. Limitations

1. Open-Meteo AQI is model-based, not always the same as a local sensor.
2. +48h and +72h errors are naturally higher.
3. Hopsworks free usage and hosting costs (Render Standard) need to be watched.
4. LSTM was trained but classical models won on most horizons for this data.

---

## 20. Future work

1. Add ground-station AQI where available
2. Category probability forecasts
3. City-specific models
4. Push notifications for alerts
5. Longer monitoring history
6. Better uptime checks for the public demo
7. Richer copilot (multi-city compare in chat, daily briefing)

---

## 21. Conclusion

I completed the internship project as a full AQI forecasting pipeline: data, features, training, Hopsworks, automation, explainability, alerts, and a deployed dashboard with a floating AQI Copilot. The app is on GitHub and runs live on Render and Vercel.

The best results are at +24h (validation R² ≈ 0.72, category accuracy ≈ 73%). Live monitoring on 3500 scored rows shows overall MAE ≈ 12.3 and category accuracy ≈ 75%. I think this is good enough for short-term air quality planning in the cities I covered.

---

## 22. Appendix — main files

| Path | Role |
|---|---|
| pipelines/feature_pipeline.py | Hourly feature refresh |
| pipelines/backfill.py | Historical training data |
| pipelines/training_pipeline.py | Model training and selection |
| pipelines/hopsworks_sync.py | Feature and model sync |
| pipelines/monitor_pipeline.py | Forecast vs actual logging |
| api/main.py | FastAPI serving |
| src/insights/copilot.py | AQI Copilot (Groq + fallback) |
| frontend/src/App.tsx | AtmoVista dashboard |
| frontend/src/components/CopilotPanel.tsx | Floating chat UI |
| artifacts/model_leaderboard.json | Training results |
| notebooks/eda.ipynb | EDA |
| .github/workflows/ | CI/CD |
| docs/AtmoVista_Internship_Report.pdf | This report |

---

*AtmoVista / Pearls AQI Predictor — internship submission.*
