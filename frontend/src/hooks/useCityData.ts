import { useEffect, useRef, useState } from "react";
import {
  api,
  type AlertItem,
  type ExerciseResponse,
  type ExplainAqiResponse,
  type ExplainCompareResponse,
  type ExplainFeature,
  type ExplainResponse,
  type ForecastResponse,
  type HealthTipsResponse,
  type HistoryPoint,
  type MonitoringSummary,
  type WeatherResponse,
} from "../api";
import type { CitySnapshot } from "../components/PakistanMap";
import { fetchForecastDeduped, getCachedForecast } from "../utils/requestCache";

export type CityDataState = {
  forecast: ForecastResponse | null;
  history: HistoryPoint[];
  alerts: AlertItem[];
  tips: HealthTipsResponse | null;
  exercise: ExerciseResponse | null;
  explainAqi: ExplainAqiResponse | null;
  weather: WeatherResponse | null;
  shap: ExplainFeature[];
  localShap: ExplainFeature[];
  localSigned: ExplainFeature[];
  explain: ExplainResponse | null;
  explainMeta: { method?: string; note?: string; narrative?: string };
  monitoring: MonitoringSummary | null;
};

export type CityLoadFlags = {
  booting: boolean;
  switching: boolean;
  forecast: boolean;
  outlook: boolean;
  history: boolean;
  health: boolean;
  insights: boolean;
  tech: boolean;
};

const EMPTY: CityDataState = {
  forecast: null,
  history: [],
  alerts: [],
  tips: null,
  exercise: null,
  explainAqi: null,
  weather: null,
  shap: [],
  localShap: [],
  localSigned: [],
  explain: null,
  explainMeta: {},
  monitoring: null,
};

const cityCache = new Map<string, CityDataState>();

function shortenFeature(name: string): string {
  return name
    .replace(/^num__/, "")
    .replace(/^city__/, "")
    .replace(/_fwd_\d+h$/, " (fwd)")
    .replace(/_/g, " ")
    .slice(0, 28);
}

function mapFeatures(list?: ExplainFeature[]): ExplainFeature[] {
  return (list ?? []).map((x) => ({
    ...x,
    feature: shortenFeature(x.feature),
    contribution: x.contribution ?? (x.direction === "down" ? -Math.abs(x.importance) : x.importance),
    importance: x.importance ?? Math.abs(x.contribution ?? 0),
  }));
}

function packFromExplain(explain: ExplainResponse, horizonHours: number): Partial<CityDataState> {
  const pack = explain.horizons?.[String(horizonHours)] ?? explain;
  const localSigned = mapFeatures(pack.local_signed ?? pack.local_features);
  return {
    explain,
    shap: mapFeatures(pack.top_features),
    localShap: mapFeatures(pack.local_features),
    localSigned,
    explainMeta: {
      method: pack.method ?? explain.method,
      note: pack.note ?? explain.note,
      narrative: pack.narrative ?? explain.narrative,
    },
  };
}

function previewFromSnapshot(city: string, snap: CitySnapshot): ForecastResponse {
  return {
    city,
    current_aqi: snap.aqi,
    current_category: snap.category,
    current_color: snap.color,
    forecast: [],
    model: "",
    event_time: new Date().toISOString(),
  };
}

function seedData(city: string, snapshot?: CitySnapshot): CityDataState {
  const cached = cityCache.get(city);
  if (cached?.forecast) return cached;
  const warmed = getCachedForecast(city);
  if (warmed) return { ...EMPTY, forecast: warmed };
  if (snapshot) {
    return { ...EMPTY, forecast: previewFromSnapshot(city, snapshot) };
  }
  return { ...EMPTY };
}

function patchCache(city: string, patch: Partial<CityDataState>) {
  const prev = cityCache.get(city) ?? { ...EMPTY };
  cityCache.set(city, { ...prev, ...patch });
}

type Options = {
  snapshot?: CitySnapshot;
  shapHorizon?: number;
};

export function useCityData(city: string, options: Options = {}) {
  const { snapshot, shapHorizon = 24 } = options;
  const requestId = useRef(0);
  const hasBooted = useRef(false);
  const shapHorizonRef = useRef(shapHorizon);
  shapHorizonRef.current = shapHorizon;

  const [data, setData] = useState<CityDataState>(() => seedData(city, snapshot));
  const [flags, setFlags] = useState<CityLoadFlags>(() => ({
    booting: true,
    switching: false,
    forecast: true,
    outlook: true,
    history: true,
    health: true,
    insights: true,
    tech: true,
  }));
  const [error, setError] = useState<string | null>(null);
  const [insightError, setInsightError] = useState(false);

  useEffect(() => {
    if (!city) return;

    const id = ++requestId.current;
    const cached = cityCache.get(city);
    const preview = !cached?.forecast?.forecast?.length ? snapshot : undefined;
    const initial = seedData(city, preview);

    setData(initial);
    setError(null);
    setInsightError(false);

    const fromCache = Boolean(cached?.forecast?.forecast?.length);
    const fromPreview = Boolean(preview && !fromCache);

    setFlags({
      booting: !hasBooted.current && !fromCache && !fromPreview,
      switching: hasBooted.current,
      forecast: !fromCache && !fromPreview,
      outlook: !fromCache,
      history: !cached?.history?.length,
      health: !cached?.tips,
      insights: !cached?.exercise,
      tech: !cached?.explain?.available && !cached?.shap?.length,
    });

    const merge = (patch: Partial<CityDataState>) => {
      if (id !== requestId.current) return;
      setData((prev) => {
        const next = { ...prev, ...patch };
        patchCache(city, patch);
        return next;
      });
    };

    const setFlag = (patch: Partial<CityLoadFlags>) => {
      if (id !== requestId.current) return;
      setFlags((prev) => ({ ...prev, ...patch }));
    };

    fetchForecastDeduped((name) => api.forecast(name), city)
      .then((forecast) => {
        if (id !== requestId.current) return;
        merge({ forecast });
        hasBooted.current = true;
        setFlag({ forecast: false, outlook: false, booting: false });
      })
      .catch((err: Error) => {
        if (id !== requestId.current) return;
        setError(err.message);
        setFlag({ forecast: false, outlook: false, booting: false });
      });

    api
      .healthTips(city)
      .then((tips) => {
        if (id !== requestId.current) return;
        merge({ tips });
        setFlag({ health: false });
      })
      .catch(() => {
        if (id !== requestId.current) return;
        setFlag({ health: false });
      });

    Promise.all([
      api.history(city),
      api.weather(city),
      api.alerts(city),
      api.exercise(city),
      api.explainAqi(city),
    ])
      .then(([historyRes, weather, alertsRes, exercise, explainAqi]) => {
        if (id !== requestId.current) return;
        merge({
          history: historyRes.points,
          weather,
          alerts: alertsRes.alerts,
          exercise,
          explainAqi,
        });
        setFlag({ history: false, insights: false });
        setInsightError(false);
      })
      .catch(() => {
        if (id !== requestId.current) return;
        setInsightError(true);
        setFlag({ history: false, insights: false });
      });

    Promise.all([api.explain(city, { horizon: 24, allHorizons: true }), api.monitoring(city)])
      .then(([explain, monitoring]) => {
        if (id !== requestId.current) return;
        merge({
          ...packFromExplain(explain, shapHorizonRef.current),
          monitoring,
        });
        setFlag({ tech: false, switching: false });
      })
      .catch(() => {
        if (id !== requestId.current) return;
        setFlag({ tech: false, switching: false });
      });

    return () => {
      if (id === requestId.current) {
        setFlag({ switching: false });
      }
    };
  }, [city]);

  useEffect(() => {
    const explain = cityCache.get(city)?.explain;
    if (!explain) return;
    const patch = packFromExplain(explain, shapHorizon);
    setData((prev) => {
      const next = { ...prev, ...patch };
      patchCache(city, patch);
      return next;
    });
  }, [shapHorizon, city]);

  return { data, flags, error, insightError };
}

export function useExplainCompare(horizon = 24) {
  const [compare, setCompare] = useState<ExplainCompareResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [requested, setRequested] = useState(false);

  useEffect(() => {
    if (!requested) return;
    let cancelled = false;
    setLoading(true);
    api
      .explainCompare(horizon)
      .then((res) => {
        if (!cancelled) setCompare(res);
      })
      .catch(() => {
        if (!cancelled) setCompare(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [requested, horizon]);

  return {
    compare,
    loading,
    load: () => setRequested(true),
    requested,
  };
}
