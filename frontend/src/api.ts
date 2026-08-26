export type City = {
  name: string;
  country: string;
  lat: number;
  lon: number;
};

export type ForecastPoint = {
  horizon_hours: number;
  target: string;
  aqi: number;
  aqi_low?: number;
  aqi_high?: number;
  interval_level?: number;
  category: string;
  color: string;
  model?: string;
};

export type ForecastResponse = {
  city: string;
  model: string;
  event_time: string;
  current_aqi: number | null;
  current_category: string;
  current_color: string;
  forecast: ForecastPoint[];
};

export type HistoryPoint = {
  event_time: string;
  aqi: number | null;
  category: string;
  pm25: number | null;
};

export type WeatherResponse = {
  city: string;
  event_time: string;
  temperature_c: number | null;
  humidity_pct: number | null;
  wind_kph: number | null;
  wind_direction_deg: number | null;
  cloud_cover_pct: number | null;
  precipitation_mm: number | null;
  pressure_hpa: number | null;
  comfort_label: string;
  air_driver: string;
  wind_label: string;
  pollutant_driver: string | null;
  pollutant_driver_detail: string;
  pollutants_top: { key: string; label: string; value: number }[];
};

export type AlertItem = {
  when: string;
  aqi: number;
  category: string;
  message: string;
};

export type LeaderboardModel = {
  name: string;
  type: string;
  val: { overall: { rmse: number; mae: number; r2: number; category_accuracy?: number } };
  test: { overall: { rmse: number; mae: number; r2: number; category_accuracy?: number } };
};

export type HealthAction = {
  id: string;
  label: string;
  detail: string;
};

export type HealthTip = {
  title: string;
  advice: string;
  actions?: HealthAction[];
  level?: string;
};

export type HealthTipsResponse = {
  city: string;
  current_category: string;
  current: HealthTip;
  forecast_tips: (HealthTip & { horizon_hours: number; category: string })[];
};

export type OpsStatus = {
  storage_mode: string;
  winner_model: string | null;
  last_train_at: string | null;
  features_updated_at: number | null;
  cities: string[];
};

export type MonitoringRecent = {
  city: string;
  horizon_hours: number;
  issued_at: string;
  target_time: string;
  predicted_aqi: number;
  actual_aqi: number;
  abs_error: number;
  category_hit: boolean;
  predicted_category?: string;
  actual_category?: string;
};

export type MonitoringSummary = {
  updated_at?: string;
  scored_rows?: number;
  pending_rows?: number;
  overall?: {
    rmse?: number;
    mae?: number;
    r2?: number;
    category_accuracy?: number;
    mean_abs_error?: number;
  };
  by_horizon?: Record<string, { mae?: number; category_accuracy?: number; n?: number; r2?: number }>;
  by_city?: Record<string, { mae?: number; category_accuracy?: number; n?: number }>;
  recent?: MonitoringRecent[];
  city_stats?: { mae?: number; category_accuracy?: number; n?: number };
};

export type SmogSeasonResponse = {
  months: {
    month: number;
    label: string;
    mean_aqi: number;
    category: string;
    color: string;
    is_peak_smog: boolean;
    is_current: boolean;
  }[];
  peak_smog_label: string;
  current_month: number;
  in_peak_season: boolean;
  headline: string;
  summary: string;
  peak_month: { label: string; mean_aqi: number };
  cleanest_month: { label: string; mean_aqi: number };
  findings?: string[];
};

export type ExplainAqiResponse = {
  aqi: number | null;
  category: string;
  color: string;
  headline: string;
  meaning: string;
  action: string;
  band?: { min: number; max: number; color: string } | null;
};

export type ExerciseResponse = {
  city: string;
  verdict: "yes" | "caution" | "no" | "unknown";
  title: string;
  reason: string;
  recommendation: string;
  intensity: string;
  current_aqi: number | null;
  current_category?: string;
  forecast_24h_aqi?: number | null;
  forecast_24h_category?: string | null;
};

export type BaselineResponse = {
  available: boolean;
  note?: string;
  winner_model?: string;
  trained_at?: string;
  horizons?: {
    horizon_hours: number;
    model: string;
    model_mae: number;
    baseline_mae: number;
    mae_improvement_pct: number;
    beats_baseline: boolean;
    model_r2: number;
    baseline_r2: number;
  }[];
  overall?: {
    horizons_beaten: number;
    horizons_total: number;
    beat_rate: number;
    avg_mae_improvement_pct: number;
    avg_rmse_improvement_pct: number;
  };
};

export type PipelineResponse = {
  overall: "green" | "yellow" | "red";
  overall_label: string;
  checks: {
    id: string;
    label: string;
    status: "green" | "yellow" | "red";
    detail: string;
    updated_at?: string | null;
  }[];
  storage_mode?: string;
  winner_model?: string | null;
};

export type CitySnapshotResponse = {
  city: string;
  current_aqi: number | null;
  current_category: string;
  current_color: string;
  event_time?: string;
};

const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`);
  if (!res.ok) {
    const body = await res.text();
    throw new Error(body || `Request failed: ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  cities: () => getJson<{ cities: City[] }>("/cities"),
  forecast: (city: string) => getJson<ForecastResponse>(`/aqi/forecast?city=${encodeURIComponent(city)}`),
  snapshots: () => getJson<{ snapshots: Record<string, CitySnapshotResponse> }>("/aqi/snapshots"),
  history: (city: string) =>
    getJson<{ city: string; points: HistoryPoint[] }>(`/aqi/history?city=${encodeURIComponent(city)}`),
  weather: (city: string) => getJson<WeatherResponse>(`/aqi/weather?city=${encodeURIComponent(city)}`),
  alerts: (city: string) =>
    getJson<{ city: string; alerts: AlertItem[]; has_alerts: boolean }>(
      `/aqi/alerts?city=${encodeURIComponent(city)}`,
    ),
  explain: (city: string) =>
    getJson<{
      available: boolean;
      city?: string;
      method?: string;
      local_method?: string;
      note?: string;
      top_features?: { feature: string; importance: number }[];
      local_features?: { feature: string; importance: number }[];
    }>(`/aqi/explain?city=${encodeURIComponent(city)}`),
  leaderboard: () =>
    getJson<{ available: boolean; winner?: string; models: LeaderboardModel[] }>("/models/leaderboard"),
  healthTips: (city: string) =>
    getJson<HealthTipsResponse>(`/aqi/health-tips?city=${encodeURIComponent(city)}`),
  opsStatus: () => getJson<OpsStatus>("/ops/status"),
  monitoring: (city?: string) =>
    getJson<MonitoringSummary>(
      city ? `/ops/monitoring?city=${encodeURIComponent(city)}` : "/ops/monitoring",
    ),
  smogSeason: () => getJson<SmogSeasonResponse>("/insights/smog-season"),
  explainAqi: (city: string) =>
    getJson<ExplainAqiResponse>(`/insights/explain-aqi?city=${encodeURIComponent(city)}`),
  exercise: (city: string) =>
    getJson<ExerciseResponse>(`/insights/exercise?city=${encodeURIComponent(city)}`),
  baseline: () => getJson<BaselineResponse>("/ops/baseline"),
  pipeline: () => getJson<PipelineResponse>("/ops/pipeline"),
};
