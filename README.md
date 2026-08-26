# AtmoVista

Internship project for AQI forecasting in Pakistan.

I built this as an end-to-end system: pull data → features → train models → store in Hopsworks → serve forecasts on a web app. The app is called **AtmoVista**.

It covers 5 cities (Lahore, Karachi, Islamabad, Peshawar, Quetta) and predicts AQI for the next 3 days (24h / 48h / 72h).

---

## What I used

- **Data:** Open-Meteo (air quality + weather) — free, no paid API key
- **Feature store / model registry:** Hopsworks
- **Models:** Ridge, Random Forest, HistGradientBoosting, LSTM (TensorFlow)
- **Backend:** FastAPI
- **Frontend:** React + Vite + TypeScript
- **Automation:** GitHub Actions (hourly features + daily training)
- **Explainability:** SHAP
- **Deploy:** Render for API, Vercel for frontend (planned / free tier)

The internship brief mentioned Streamlit or Gradio. I went with FastAPI + React instead for a proper custom UI.

---

## Folder structure

```
aqi-predictor/
  api/                 FastAPI app
  src/                 data fetch, features, training, inference, insights
  pipelines/           backfill, feature, training, monitoring, hopsworks sync
  frontend/            AtmoVista UI
  notebooks/           EDA
  artifacts/           models, leaderboard, shap stuff
  docs/                my internship report
  .github/workflows/   automation
```

---

## Setup (local)

1. Create a `.env` in the project root (don’t commit this):

```
HOPSWORKS_API_KEY=your_key
HOPSWORKS_PROJECT=mateen_pearls_aqi
HOPSWORKS_HOST=eu-west.cloud.hopsworks.ai
STORAGE_MODE=hopsworks
API_HOST=0.0.0.0
API_PORT=8000
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

2. Python side:

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

3. If you need to rebuild data / models from scratch:

```bash
python pipelines/backfill.py --days 90
python pipelines/training_pipeline.py --lstm-epochs 8
python pipelines/hopsworks_sync.py
```

4. Start API:

```bash
uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

5. Start frontend:

```bash
cd frontend
npm install
npm run dev
```

Optional: put `VITE_API_URL=http://127.0.0.1:8000` in `frontend/.env`  
Then open http://127.0.0.1:5173

---

## Main API endpoints

Most of these take `?city=Lahore` (or another city):

- `/health`
- `/cities`
- `/aqi/forecast`
- `/aqi/history`
- `/aqi/weather`
- `/aqi/explain` (SHAP)
- `/aqi/alerts`
- `/aqi/health-tips`
- `/models/leaderboard`
- `/ops/status`
- `/ops/monitoring`

---

## About the UI

Two modes:

- **For you** — map, current AQI, 3-day forecast, weather, health tips, alerts, exercise advice
- **For experts** — leaderboard, SHAP, baseline comparison, pipeline status, live accuracy

---

## GitHub Actions

Secrets used: `HOPSWORKS_API_KEY`, `HOPSWORKS_PROJECT` (and host if needed).

Workflows running on the repo:

- `feature-hourly.yml` — refresh features + monitoring
- `training-daily.yml` — retrain + sync to Hopsworks
- `monitor-daily.yml`

---

## Deploy

- Repo on GitHub with Actions (hourly features + daily training)
- Frontend on Vercel (`frontend/`)
- API on Render (`render.yaml`, `STORAGE_MODE=hopsworks`)
- Features/models live on Hopsworks (API caches in memory; no committed parquet needed)

---

## Report

More detail on what I built, EDA, and results:

- [docs/AtmoVista_Internship_Report.md](docs/AtmoVista_Internship_Report.md)
- [docs/AtmoVista_Internship_Report.pdf](docs/AtmoVista_Internship_Report.pdf)
