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

export type PollutantReading = {
  key: string;
  label: string;
  value: number;
  unit: string;
  intensity_pct: number;
  level: string;
  color: string;
  is_dominant: boolean;
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
  pollutants?: PollutantReading[];
  pollutants_top: { key: string; label: string; value: number }[];
};

export type AlertItem = {
  when: string;
  aqi: number;
  category: string;
  message: string;
};

export type ExplainFeature = {
  feature: string;
  importance: number;
  contribution?: number;
  direction?: "up" | "down" | "neutral";
  glossary?: string;
  raw_feature?: string;
};

export type ExplainWaterfall = {
  base_value: number;
  prediction: number;
  residual?: number;
  steps: {
    feature: string;
    contribution: number;
    direction?: string;
    glossary?: string;
    before: number;
    after: number;
  }[];
};

export type ExplainHorizonPack = {
  available: boolean;
  horizon_hours?: number;
  model?: string;
  method?: string;
  local_method?: string;
  note?: string;
  error?: string;
  prediction?: number;
  event_time?: string;
  top_features?: ExplainFeature[];
  local_features?: ExplainFeature[];
  local_signed?: ExplainFeature[];
  waterfall?: ExplainWaterfall | null;
  narrative?: string;
  pollutant_link?: {
    shap_pollutant_features?: { feature: string; key: string; direction: string }[];
    dominant_pollutant?: string | null;
    agree?: boolean;
    note?: string;
  };
};

export type ExplainResponse = ExplainHorizonPack & {
  city?: string;
  horizon?: string;
  horizon_hours?: number;
  horizons?: Record<string, ExplainHorizonPack>;
  horizons_hours?: number[];
  global_summary?: {
    available: boolean;
    method?: string;
    note?: string;
    top_features?: ExplainFeature[];
  };
  glossary?: Record<string, string>;
};

export type ExplainCompareResponse = {
  available: boolean;
  horizon_hours: number;
  note?: string;
  cities: {
    city: string;
    available: boolean;
    prediction?: number;
    narrative?: string;
    top_features?: ExplainFeature[];
    error?: string;
  }[];
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

function isRetriableNetworkError(message: string): boolean {
  const msg = message.toLowerCase();
  return (
    msg.includes("failed to fetch") ||
    msg.includes("networkerror") ||
    msg.includes("load failed") ||
    msg.includes("502") ||
    msg.includes("503") ||
    msg.includes("504") ||
    msg.includes("timeout") ||
    msg.includes("aborted")
  );
}

/** Retry briefly on network blips; Starter should already be awake. */
async function getJson<T>(path: string, retries = 4): Promise<T> {
  let lastError: Error | null = null;
  for (let attempt = 1; attempt <= retries; attempt++) {
    try {
      const res = await fetch(`${API_URL}${path}`);
      if (!res.ok) {
        const body = await res.text();
        throw new Error(body || `Request failed: ${res.status}`);
      }
      return (await res.json()) as T;
    } catch (err) {
      lastError = err instanceof Error ? err : new Error(String(err));
      if (!isRetriableNetworkError(lastError.message) || attempt >= retries) break;
      const delayMs = Math.min(800 * attempt, 2500);
      await new Promise((r) => setTimeout(r, delayMs));
    }
  }
  throw lastError ?? new Error("Request failed");
}

/** Soft ping — do not block the UI on this. */
export async function wakeApi(): Promise<boolean> {
  try {
    await getJson<{ status: string }>("/health", 3);
    return true;
  } catch {
    return false;
  }
}

export const api = {
  health: () => getJson<{ status: string; project?: string }>("/health"),
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
  explain: (city: string, opts?: { horizon?: number; allHorizons?: boolean }) => {
    const horizon = opts?.horizon ?? 24;
    const all = opts?.allHorizons ?? true;
    return getJson<ExplainResponse>(
      `/aqi/explain?city=${encodeURIComponent(city)}&horizon=${horizon}&all_horizons=${all}`,
    );
  },
  explainCompare: (horizon = 24) =>
    getJson<ExplainCompareResponse>(`/aqi/explain/compare?horizon=${horizon}`),
  explainGlobal: () =>
    getJson<ExplainResponse["global_summary"] & object>(`/aqi/explain/global`),
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
