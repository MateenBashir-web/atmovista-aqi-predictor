import { useEffect, useMemo, useRef, useState, startTransition, type CSSProperties } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  api,
  wakeApi,
  type BaselineResponse,
  type City,
  type ForecastResponse,
  type LeaderboardModel,
  type OpsStatus,
  type PipelineResponse,
  type SmogSeasonResponse,
} from "./api";
import { BRAND } from "./brand";
import {
  BaselinePanel,
  ExerciseCard,
  ExplainAqiModal,
  PipelinePanel,
  SmogSeasonPanel,
} from "./components/InsightPanels";
import { PakistanMap } from "./components/PakistanMap";
import { useAnimatedNumber } from "./hooks/useAnimatedNumber";
import { useCityData } from "./hooks/useCityData";
import { useCitySnapshots } from "./hooks/useCitySnapshots";
import { useTheme } from "./hooks/useTheme";
import { useViewMode } from "./hooks/useViewMode";
import { useWatchlist } from "./hooks/useWatchlist";
import { AQI_LEGEND } from "./utils/aqiLegend";
import { exportForecastPng } from "./utils/exportCard";
import { formatRelativeTime, formatHorizonDay, formatHorizonChartLabel, formatDayLabel, parseHorizonHours } from "./utils/time";
import "./index.css";

const GAUGE_MAX = 300;
const GAUGE_CIRC = 2 * Math.PI * 72;

function severityClass(category?: string | null): string {
  if (!category) return "sev-unknown";
  if (category === "Good") return "sev-good";
  if (category === "Moderate") return "sev-moderate";
  if (category.includes("Sensitive")) return "sev-sensitive";
  if (category === "Unhealthy") return "sev-unhealthy";
  if (category === "Very Unhealthy") return "sev-very";
  if (category === "Hazardous") return "sev-hazard";
  return "sev-unknown";
}

function formatModelName(name?: string | null): string {
  if (!name) return "—";
  if (name.length <= 48) return name;
  return name.replace(/\+/g, " · ").slice(0, 52) + "…";
}

function shortModelLabel(name?: string | null): string {
  if (!name) return "Ready";
  const cleaned = name.replace(/_/g, " ");
  if (cleaned.length <= 22) return cleaned;
  return `${cleaned.slice(0, 20)}…`;
}

function formatWindDirection(deg?: number | null): string {
  if (deg == null || Number.isNaN(deg)) return "—";
  const dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
  return dirs[Math.round(deg / 45) % 8];
}

function aqiScalePercent(aqi: number | null | undefined): number {
  if (aqi == null || Number.isNaN(aqi)) return 0;
  return Math.min(100, Math.max(0, (aqi / GAUGE_MAX) * 100));
}

function bandMatchesCategory(bandLabel: string, category?: string | null): boolean {
  if (!category) return false;
  if (bandLabel === "Sensitive") return category.includes("Sensitive");
  return category === bandLabel || category.startsWith(bandLabel);
}

function AqiColorLegend({
  compact = false,
  bands = false,
  activeCategory,
}: {
  compact?: boolean;
  bands?: boolean;
  activeCategory?: string | null;
}) {
  if (bands) {
    return (
      <div className="aqi-band-grid" aria-label="AQI category bands">
        {AQI_LEGEND.map((item) => {
          const active = bandMatchesCategory(item.label, activeCategory);
          return (
            <div
              className={`aqi-band-cell ${active ? "is-active" : ""}`}
              key={item.label}
              style={{ ["--band-color" as string]: item.color }}
              title={`${item.label} · ${item.range}`}
            >
              <span className="aqi-band-swatch" style={{ background: item.color }} />
              <span className="aqi-band-name">{item.label}</span>
              <span className="aqi-band-range">{item.range}</span>
            </div>
          );
        })}
      </div>
    );
  }

  return (
    <div className={`aqi-legend ${compact ? "compact" : ""}`} aria-label="AQI color legend">
      {AQI_LEGEND.map((item) => (
        <div className="aqi-legend-item" key={item.label} title={`${item.label} · ${item.range}`}>
          <span className="aqi-legend-swatch" style={{ background: item.color }} />
          <span className="aqi-legend-label">{item.label}</span>
          {!compact && <span className="aqi-legend-range">{item.range}</span>}
        </div>
      ))}
    </div>
  );
}

function ChartSkeleton({ height = 280 }: { height?: number }) {
  return (
    <div className="skeleton-block chart-skeleton" style={{ height }} aria-hidden="true">
      <div className="skeleton-line" style={{ width: "40%" }} />
      <div className="skeleton-bars">
        <span style={{ height: "45%" }} />
        <span style={{ height: "70%" }} />
        <span style={{ height: "55%" }} />
        <span style={{ height: "85%" }} />
        <span style={{ height: "60%" }} />
        <span style={{ height: "75%" }} />
      </div>
    </div>
  );
}

function MapSkeleton() {
  return (
    <div className="skeleton-block map-skeleton" aria-hidden="true">
      <div className="skeleton-map-shape" />
      <div className="skeleton-line" style={{ width: "55%", margin: "0.75rem auto 0" }} />
    </div>
  );
}

function RankingsSkeleton() {
  return (
    <div className="map-legend" aria-hidden="true">
      {[1, 2, 3, 4, 5].map((i) => (
        <div className="map-legend-item skeleton-row" key={i}>
          <span className="skeleton" style={{ width: 10, height: 10, borderRadius: "50%" }} />
          <span className="skeleton" style={{ height: 14, width: "40%" }} />
          <span className="skeleton" style={{ height: 18, width: 36 }} />
          <span className="skeleton" style={{ height: 12, width: 48 }} />
        </div>
      ))}
    </div>
  );
}

function BrandMark() {
  return (
    <svg viewBox="0 0 32 32" fill="none" aria-hidden="true">
      <circle cx="16" cy="16" r="11" stroke="currentColor" strokeWidth="1.5" opacity="0.35" />
      <path
        d="M7 18c3-4 7-6 9-6s6 2 9 6"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
      <path
        d="M9 22c2-2.5 5-4 7-4s5 1.5 7 4"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        opacity="0.65"
      />
      <circle cx="16" cy="12" r="2.5" fill="currentColor" />
    </svg>
  );
}

function AnimatedNumber({
  value,
  decimals = 0,
  loading,
  className,
  style,
}: {
  value: number | null | undefined;
  decimals?: number;
  loading?: boolean;
  className?: string;
  style?: CSSProperties;
}) {
  const text = useAnimatedNumber(loading ? null : value, { decimals, enabled: !loading });
  return (
    <span className={`num-animate ${className ?? ""}`.trim()} style={style}>
      {loading ? "—" : text}
    </span>
  );
}

function AqiGauge({
  value,
  color,
  loading,
}: {
  value: number | null | undefined;
  color: string;
  loading: boolean;
}) {
  const pct = aqiScalePercent(value);
  const offset = GAUGE_CIRC - (pct / 100) * GAUGE_CIRC;

  return (
    <div className="aqi-gauge" aria-hidden={loading}>
      <svg viewBox="0 0 160 160">
        <circle className="aqi-gauge-track" cx="80" cy="80" r="72" />
        <circle
          className="aqi-gauge-fill"
          cx="80"
          cy="80"
          r="72"
          stroke={color}
          strokeDasharray={GAUGE_CIRC}
          strokeDashoffset={loading ? GAUGE_CIRC : offset}
        />
      </svg>
      <div className="aqi-gauge-center">
        <AnimatedNumber
          value={value}
          className={`aqi-number ${loading ? "skeleton" : ""}`}
          style={{ color, fontSize: "2.75rem", fontFamily: "var(--font-display)", fontWeight: 700 }}
          loading={loading}
        />
        <span className="aqi-unit">AQI Index</span>
      </div>
    </div>
  );
}

function ChartTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: { name?: string; value?: number | string; color?: string; stroke?: string; fill?: string }[];
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="chart-tooltip">
      {label && <div className="chart-tooltip-label">{label}</div>}
      {payload.map((p) => (
        <div key={String(p.name)} className="chart-tooltip-value">
          <span
            className="chart-tooltip-dot"
            style={{ background: p.color || p.stroke || p.fill || "var(--accent)" }}
          />
          <span className="chart-tooltip-name">{p.name}</span>
          <strong className="chart-tooltip-num">
            {typeof p.value === "number" ? p.value.toFixed(1) : p.value}
          </strong>
        </div>
      ))}
    </div>
  );
}

function App() {
  const { toggle, isDark } = useTheme();
  const { mode, setMode, isEveryday, isTechnical } = useViewMode();
  const { watchlist, toggleCity, maxWatchlistItems } = useWatchlist();
  const [cities, setCities] = useState<City[]>([]);
  const [city, setCity] = useState("Lahore");
  const { snapshots: citySnapshots, mapLoading, mapRefreshing, patchSnapshot } =
    useCitySnapshots(cities, city);
  const citySnapshot = citySnapshots[city];
  const {
    data: cityData,
    flags: loadFlags,
    error: cityError,
    insightError,
  } = useCityData(city, { snapshot: citySnapshot });
  const {
    forecast,
    history,
    alerts,
    tips,
    exercise,
    explainAqi,
    weather,
    shap,
    localShap,
    explainMeta,
    monitoring,
  } = cityData;
  const [leaderboard, setLeaderboard] = useState<{ winner?: string; models: LeaderboardModel[] }>({
    models: [],
  });
  const [ops, setOps] = useState<OpsStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [waking, setWaking] = useState(true);
  const [toast, setToast] = useState<string | null>(null);
  const [nowTick, setNowTick] = useState(0);
  const [exporting, setExporting] = useState(false);
  const [opsOpen, setOpsOpen] = useState(false);
  const [smogSeason, setSmogSeason] = useState<SmogSeasonResponse | null>(null);
  const [explainOpen, setExplainOpen] = useState(false);
  const openExplainModal = () => {
    startTransition(() => setExplainOpen(true));
  };

  const closeExplainModal = () => setExplainOpen(false);
  const [baseline, setBaseline] = useState<BaselineResponse | null>(null);
  const [pipeline, setPipeline] = useState<PipelineResponse | null>(null);
  const [smogError, setSmogError] = useState(false);
  const toastTimer = useRef<number | null>(null);
  const skipToastRef = useRef(true);

  useEffect(() => {
    const id = window.setInterval(() => setNowTick((n) => n + 1), 30_000);
    return () => window.clearInterval(id);
  }, []);

  useEffect(() => {
    const els = Array.from(document.querySelectorAll<HTMLElement>(".reveal"));
    if (!els.length) return;

    els.forEach((el) => el.classList.remove("in-view"));

    let allowReveals = false;
    let lastScrollY = window.scrollY || 0;
    const syncReveals = () => {
      const viewportH = window.innerHeight || 800;
      const currScrollY = window.scrollY || 0;
      const scrollingDown = currScrollY >= lastScrollY;
      lastScrollY = currScrollY;

      const enterLine = viewportH * 0.85;
      const exitLine = viewportH * 0.35;

      for (const el of els) {
        const r = el.getBoundingClientRect();
        if (scrollingDown) {
          if (r.top <= enterLine && r.bottom > 0) {
            el.classList.add("in-view");
          }
        } else {
          if (r.top > exitLine) {
            el.classList.remove("in-view");
          }
        }
      }
    };

    const onScroll = () => {
      const y = window.scrollY || document.documentElement.scrollTop || 0;
      if (!allowReveals && y > 30) {
        allowReveals = true;
      }
      if (!allowReveals) return;
      syncReveals();
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", syncReveals);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", syncReveals);
    };
  }, [mode, isEveryday, isTechnical]);

  const showCityToast = (name: string) => {
    if (skipToastRef.current) {
      skipToastRef.current = false;
      return;
    }
    setToast(`Viewing ${name}`);
    if (toastTimer.current) window.clearTimeout(toastTimer.current);
    toastTimer.current = window.setTimeout(() => setToast(null), 2200);
  };

  const selectCity = (name: string) => {
    if (name === city) return;
    setCity(name);
    showCityToast(name);
  };

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setWaking(true);
      const awake = await wakeApi();
      if (cancelled) return;
      setWaking(false);
      if (!awake) {
        setError("API_WAKE_FAILED");
        return;
      }
      setError(null);
      try {
        const res = await api.cities();
        if (cancelled) return;
        setCities(res.cities);
        if (res.cities.length) setCity(res.cities[0].name);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      }
      api.opsStatus().then(setOps).catch(() => undefined);
      api.leaderboard().then((l) => setLeaderboard({ winner: l.winner, models: l.models ?? [] })).catch(() => undefined);
      api
        .smogSeason()
        .then((s) => {
          setSmogSeason(s);
          setSmogError(false);
        })
        .catch(() => setSmogError(true));
      api.baseline().then(setBaseline).catch(() => undefined);
      api.pipeline().then(setPipeline).catch(() => undefined);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (cityError) setError(cityError);
    else if (forecast) setError(null);
  }, [cityError, forecast]);

  useEffect(() => {
    if (!forecast || !cities.length) return;
    const c = cities.find((x) => x.name === forecast.city);
    if (!c) return;
    patchSnapshot(forecast.city, {
      name: forecast.city,
      aqi: forecast.current_aqi,
      category: forecast.current_category,
      color: forecast.current_color,
      lat: c.lat,
      lon: c.lon,
    });
  }, [forecast, cities, patchSnapshot]);

  const historyChart = useMemo(
    () =>
      history
        .filter((p) => p.aqi != null)
        .map((p) => ({
          time: new Date(p.event_time).toLocaleString(undefined, {
            month: "short",
            day: "numeric",
            hour: "2-digit",
          }),
          aqi: p.aqi,
        })),
    [history],
  );

  const shapChart = useMemo(() => shap.slice(0, 8), [shap]);
  const localShapChart = useMemo(() => localShap.slice(0, 8), [localShap]);

  const forecastTrend = useMemo(() => {
    const points = forecast?.forecast ?? [];
    const current = forecast?.current_aqi;
    const base = forecast?.event_time;
    const rows: { label: string; aqi: number | null; aqiLow: number | null; aqiHigh: number | null; aqiRange: number; color?: string }[] = [
      {
        label: base ? `Now · ${formatHorizonChartLabel(base, 0)}` : "Now",
        aqi: current ?? null,
        aqiLow: current ?? null,
        aqiHigh: current ?? null,
        aqiRange: 0,
        color: forecast?.current_color,
      },
      ...points.map((f) => ({
        label: formatHorizonChartLabel(base, f.horizon_hours),
        aqi: f.aqi,
        aqiLow: f.aqi_low ?? f.aqi,
        aqiHigh: f.aqi_high ?? f.aqi,
        aqiRange: Math.max(0, (f.aqi_high ?? f.aqi) - (f.aqi_low ?? f.aqi)),
        color: f.color,
      })),
    ];
    return rows;
  }, [forecast]);

  const bestModelName = useMemo(() => {
    if (!leaderboard.models.length) return null;
    return leaderboard.models.reduce((a, b) =>
      a.val.overall.rmse <= b.val.overall.rmse ? a : b,
    ).name;
  }, [leaderboard.models]);

  const themeClass = severityClass(forecast?.current_category);
  const accentColor = forecast?.current_color || "#3ecfb2";
  const scalePct = aqiScalePercent(forecast?.current_aqi);
  const modelFull = ops?.winner_model || forecast?.model || "";

  void nowTick;

  const updatedRelative = formatRelativeTime(forecast?.event_time);
  const updatedExact = forecast?.event_time
    ? new Date(forecast.event_time).toLocaleString(undefined, {
        dateStyle: "medium",
        timeStyle: "short",
      })
    : "—";

  const downloadForecastTxt = () => {
    if (!forecast) return;
    const lines = [
      BRAND.name,
      BRAND.tagline,
      "",
      `City: ${forecast.city}`,
      `Current AQI: ${forecast.current_aqi} (${forecast.current_category})`,
      ...forecast.forecast.map((f) => {
        const range =
          f.aqi_low != null && f.aqi_high != null ? ` range ${f.aqi_low}-${f.aqi_high}` : "";
        const day = formatHorizonDay(forecast.event_time, f.horizon_hours);
        return `+${f.horizon_hours}h (${day}): ${f.aqi}${range} (${f.category})`;
      }),
      `Model: ${forecast.model}`,
      `Updated: ${forecast.event_time}`,
    ];
    const blob = new Blob([lines.join("\n")], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `atmovista-${forecast.city.toLowerCase()}-forecast.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const shareForecastPng = async () => {
    if (!forecast) return;
    setExporting(true);
    try {
      await exportForecastPng(forecast);
      setToast("Forecast card saved");
      if (toastTimer.current) window.clearTimeout(toastTimer.current);
      toastTimer.current = window.setTimeout(() => setToast(null), 2200);
    } finally {
      setExporting(false);
    }
  };

  const maeDisplay =
    monitoring?.city_stats?.mae ??
    monitoring?.overall?.mean_abs_error ??
    monitoring?.overall?.mae;
  const catAcc =
    monitoring?.city_stats?.category_accuracy ?? monitoring?.overall?.category_accuracy;

  const heroLoading = loadFlags.booting || (loadFlags.forecast && forecast?.current_aqi == null);
  const outlookLoading = loadFlags.outlook && !forecast?.forecast?.length;
  const historyLoading = loadFlags.history && !historyChart.length;
  const healthLoading = loadFlags.health && !tips;
  const techLoading = loadFlags.tech && !shapChart.length;
  const switching = loadFlags.switching;
  const rankedSnapshots = useMemo(
    () =>
      (cities.length
        ? cities
        : [{ name: city, country: "Pakistan", lat: 31.52, lon: 74.36 } as City]
      )
        .map((c) => ({ city: c, snap: citySnapshots[c.name] }))
        .filter((row) => row.snap?.aqi != null)
        .sort((a, b) => (a.snap?.aqi ?? 999) - (b.snap?.aqi ?? 999)),
    [cities, city, citySnapshots],
  );
  const cleanestCity = rankedSnapshots[0];
  const worstCity = rankedSnapshots[rankedSnapshots.length - 1];
  const currentRank = rankedSnapshots.findIndex((row) => row.city.name === city);
  const watchlistRows = useMemo(
    () =>
      watchlist
        .map((name) => {
          const rowCity = cities.find((item) => item.name === name);
          return rowCity ? { city: rowCity, snap: citySnapshots[name] } : null;
        })
        .filter(Boolean) as { city: City; snap?: (typeof citySnapshots)[string] }[],
    [watchlist, cities, citySnapshots],
  );
  const forecastDirection = useMemo(() => {
    const next = forecast?.forecast?.[0]?.aqi;
    const now = forecast?.current_aqi;
    if (next == null || now == null) return null;
    const diff = next - now;
    if (Math.abs(diff) < 6) return { label: "Holding steady", tone: "stable", detail: "Little change expected in 24h" };
    if (diff > 0) return { label: "May worsen next", tone: "warn", detail: `Up about ${Math.round(diff)} AQI in 24h` };
    return { label: "May improve next", tone: "good", detail: `Down about ${Math.round(Math.abs(diff))} AQI in 24h` };
  }, [forecast]);
  const watchlistFull = !watchlist.includes(city) && watchlist.length >= maxWatchlistItems;
  const confidenceInsight = useMemo(() => {
    const points = forecast?.forecast?.filter((item) => item.aqi_low != null && item.aqi_high != null) ?? [];
    if (!points.length) return null;
    const widest = points.reduce((a, b) => ((a.aqi_high! - a.aqi_low!) >= (b.aqi_high! - b.aqi_low!) ? a : b));
    const spread = widest.aqi_high! - widest.aqi_low!;
    const day = formatHorizonDay(forecast?.event_time, widest.horizon_hours);
    return {
      label: spread <= 15 ? "Tight confidence" : spread <= 35 ? "Moderate spread" : "Wider uncertainty",
      detail: `Range is widest on ${day} (+${widest.horizon_hours}h): ${Math.round(widest.aqi_low!)}–${Math.round(widest.aqi_high!)} AQI.`,
      tone: spread <= 15 ? "good" : spread <= 35 ? "stable" : "warn",
    };
  }, [forecast]);
  const cityConditionsSummary = useMemo(() => {
    const temp =
      weather?.temperature_c != null
        ? weather.temperature_c >= 32
          ? "hot"
          : weather.temperature_c >= 24
            ? "warm"
            : "cool"
        : "variable";
    const humidity =
      weather?.humidity_pct != null
        ? weather.humidity_pct >= 75
          ? "very humid"
          : weather.humidity_pct >= 55
            ? "humid"
            : "drier"
        : "mixed";
    const wind =
      weather?.wind_kph != null
        ? weather.wind_kph >= 18
          ? "under breezy winds"
          : weather.wind_kph >= 8
            ? "with light winds"
            : "under still air"
        : "with changing winds";
    const air = forecastDirection?.label
      ? forecastDirection.label === "Holding steady"
        ? "AQI should stay fairly steady next."
        : `${forecastDirection.label} over the next 24 hours.`
      : "AQI outlook is updating.";
    return `${city} is ${temp}, ${humidity}, and ${wind}. ${air}`;
  }, [city, weather, forecastDirection]);
  const peakInsight = useMemo(() => {
    const points = forecast?.forecast ?? [];
    if (!points.length) return null;
    const peak = points.reduce((a, b) => (a.aqi >= b.aqi ? a : b));
    const day = formatHorizonDay(forecast?.event_time, peak.horizon_hours);
    return {
      label: "Expected peak",
      value: day,
      detail: `+${peak.horizon_hours}h · ${Math.round(peak.aqi)} AQI · ${peak.category}`,
      tone:
        peak.category === "Good"
          ? "good"
          : peak.category === "Moderate"
            ? "stable"
            : peak.category.includes("Sensitive")
              ? "warn"
              : "risk",
    };
  }, [forecast]);
  const dropInsight = useMemo(() => {
    const now = forecast?.current_aqi;
    const points = forecast?.forecast ?? [];
    if (now == null || !points.length) return null;
    const best = points.reduce((acc, item) => {
      const delta = now - item.aqi;
      if (!acc || delta > acc.delta) return { delta, item };
      return acc;
    }, null as null | { delta: number; item: (typeof points)[number] });
    if (!best || best.delta <= 4) {
      return {
        label: "Improvement window",
        value: "Small shift",
        detail: "No major drop is projected over the next 72 hours.",
        tone: "stable",
      };
    }
    const day = formatHorizonDay(forecast?.event_time, best.item.horizon_hours);
    return {
      label: "Improvement window",
      value: day,
      detail: `+${best.item.horizon_hours}h · about ${Math.round(best.delta)} AQI lower than now.`,
      tone: "good",
    };
  }, [forecast]);
  const summaryCards = [
    {
      label: "Right now",
      value: forecast?.current_category || "Loading",
      detail: forecast?.current_aqi != null ? `AQI ${Math.round(forecast.current_aqi)} in ${city}` : "Live city reading",
      tone:
        forecast?.current_category === "Good"
          ? "good"
          : forecast?.current_category === "Moderate"
            ? "warn"
            : "risk",
    },
    {
      label: "Next 24h",
      value: forecastDirection?.label || "Updating",
      detail: forecastDirection?.detail || "Fresh forecast arriving",
      tone: forecastDirection?.tone || "stable",
    },
    {
      label: "Weather now",
      value: weather?.temperature_c != null ? `${Math.round(weather.temperature_c)}°C` : "Updating",
      detail:
        weather?.humidity_pct != null && weather?.wind_kph != null
          ? `${weather.humidity_pct}% humidity · ${Math.round(weather.wind_kph)} km/h wind`
          : "Live city weather context",
      tone:
        weather?.wind_kph != null && weather.wind_kph >= 18
          ? "good"
          : weather?.humidity_pct != null && weather.humidity_pct >= 75
            ? "warn"
            : "stable",
    },
    {
      label: "Pakistan rank",
      value:
        currentRank >= 0 && rankedSnapshots.length
          ? `${currentRank + 1}/${rankedSnapshots.length}`
          : "—",
      detail:
        currentRank === 0
          ? `${city} is the cleanest monitored city now`
          : currentRank === rankedSnapshots.length - 1 && currentRank >= 0
            ? `${city} is the most polluted monitored city now`
            : cleanestCity
              ? `Cleaner than ${rankedSnapshots.length - currentRank - 1} cities right now`
              : "Comparing live city readings",
      tone: currentRank === 0 ? "good" : currentRank === rankedSnapshots.length - 1 ? "risk" : "stable",
    },
  ];
  const cityHighlights = [
    cleanestCity && {
      kicker: "Cleanest now",
      city: cleanestCity.city.name,
      value: cleanestCity.snap?.aqi,
      note: cleanestCity.snap?.category || "—",
      tone: "good",
    },
    worstCity && {
      kicker: "Needs attention",
      city: worstCity.city.name,
      value: worstCity.snap?.aqi,
      note: worstCity.snap?.category || "—",
      tone: "risk",
    },
    forecast && {
      kicker: "Selected city",
      city,
      value: forecast.current_aqi,
      note: forecastDirection?.label || "Current AQI outlook",
      tone: forecastDirection?.tone || "stable",
    },
  ].filter(Boolean) as {
    kicker: string;
    city: string;
    value: number | null | undefined;
    note: string;
    tone: string;
  }[];

  return (
    <>
      <div className="ambient-bg" aria-hidden="true" />
      <div className="ambient-grid" aria-hidden="true" />
      <div className="orb orb-1" aria-hidden="true" />
      <div className="orb orb-2" aria-hidden="true" />
      <div className="orb orb-3" aria-hidden="true" />

      <div
        className={`app-shell mode-${mode} ${themeClass} ${loadFlags.booting ? "is-booting" : ""} ${switching ? "is-switching" : ""}`}
      >
        {toast && (
          <div className="toast" role="status" aria-live="polite">
            {toast}
        </div>
        )}

        <header className="site-header">
          <div className="header-inner">
            <div className="brand-lockup">
              <div className="brand-mark" style={{ color: accentColor }}>
                <BrandMark />
        </div>
              <div className="brand-text">
                <h1 className="brand">
                  <span className="accent-word">{BRAND.name}</span>
                </h1>
                <p className="tagline">
                  {isEveryday
                    ? "Know your air — forecasts & health guidance"
                    : "Models · explainability · live accuracy"}
          </p>
        </div>
            </div>
            <div className="header-actions">
              <div className="mode-switch" role="tablist" aria-label="View mode">
                <button
                  type="button"
                  role="tab"
                  className={`mode-tab ${isEveryday ? "active" : ""}`}
                  aria-selected={isEveryday}
                  onClick={() => setMode("everyday")}
                >
                  For you
                </button>
                <button
                  type="button"
                  role="tab"
                  className={`mode-tab ${isTechnical ? "active" : ""}`}
                  aria-selected={isTechnical}
                  onClick={() => setMode("technical")}
                >
                  For experts
                </button>
        </div>
        <button
          type="button"
                className="theme-toggle"
                onClick={toggle}
                aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
                title={isDark ? "Light mode" : "Dark mode"}
              >
                {isDark ? "☀" : "☾"}
              </button>
              <div className="live-badge">
                <span className="pulse-dot" />
                Live
              </div>
            </div>
          </div>
        </header>

        <nav className="city-bar sticky-cities" aria-label="City selection">
          <p className="city-bar-label">
            Select city
            {switching && (
              <span className="city-bar-sync" aria-live="polite">
                Updating…
              </span>
            )}
          </p>
          <div className="city-switch" role="tablist">
            {(cities.length ? cities : [{ name: city } as City]).map((c) => (
              <button
                key={c.name}
                className={`city-chip ${c.name === city ? "active" : ""} ${c.name === city && switching ? "is-syncing" : ""}`}
                onClick={() => selectCity(c.name)}
                type="button"
                role="tab"
                aria-selected={c.name === city}
              >
                {c.name}
              </button>
            ))}
          </div>
        </nav>

        {(waking || error) && (
          <div
            className={`status-banner ${error && !waking ? "is-error" : "is-wake"}`}
            role="status"
            aria-live="polite"
          >
            {waking ? (
              <>
                <span className="status-spinner" aria-hidden />
                Starting the forecast server… this can take up to a minute on the free plan.
              </>
            ) : (
              <>
                <span>
                  Couldn’t reach the forecast API. It may still be starting — wait a moment, then try again.
                </span>
                <button type="button" className="btn status-retry" onClick={() => window.location.reload()}>
                  Retry now
                </button>
              </>
            )}
          </div>
        )}

        {isTechnical && (
          <div className="tech-context panel reveal reveal-1">
            <div className="tech-context-main">
              <p className="section-kicker">Active city</p>
              <p className="city-display">
                {city}
                <span>
                  AQI {forecast?.current_aqi ?? "—"} · {forecast?.current_category || "—"} · updated{" "}
                  {heroLoading ? "…" : updatedRelative}
                </span>
              </p>
            </div>
            <button type="button" className="btn" onClick={() => setMode("everyday")}>
              ← For you
            </button>
          </div>
        )}

        {isEveryday && (
          <>
        <section className="summary-strip reveal reveal-1">
          {summaryCards.map((card) => (
            <div className={`summary-card tone-${card.tone}`} key={card.label}>
              <p className="summary-label">{card.label}</p>
              <strong className="summary-value">{card.value}</strong>
              <span className="summary-detail">{card.detail}</span>
            </div>
          ))}
        </section>

        <section className="panel watchlist-panel reveal reveal-1">
          <div className="watchlist-head">
        <div>
              <p className="section-kicker">Your cities</p>
              <h2 className="section-title">Quick watchlist</h2>
            </div>
            <button
              type="button"
              className={`btn btn-watch ${watchlist.includes(city) ? "active" : ""}`}
              onClick={() => toggleCity(city)}
              title={watchlist.includes(city) ? "Remove from watchlist" : "Add this city to watchlist"}
            >
              {watchlist.includes(city) ? "★ Pinned" : watchlistFull ? "Watchlist full" : "☆ Pin city"}
            </button>
          </div>
          <p className="section-sub">
            Keep up to {maxWatchlistItems} favorite cities for quick AQI checks.
          </p>
          {!watchlistRows.length ? (
            <div className="empty-state">Pin cities to build your personal AQI watchlist.</div>
          ) : (
            <div className="watchlist-grid watchlist-rail">
              {watchlistRows.map(({ city: watchCity, snap }) => (
                <button
                  key={watchCity.name}
                  type="button"
                  className={`watchlist-card ${watchCity.name === city ? "active" : ""}`}
                  onClick={() => selectCity(watchCity.name)}
                >
                  <div className="watchlist-card-top">
                    <strong>{watchCity.name}</strong>
                    <span
                      className="watchlist-dot"
                      style={{ background: snap?.color || "#94a3b8" }}
                    />
        </div>
                  <div className="watchlist-main">
                    <span className="watchlist-aqi">
                      <AnimatedNumber value={snap?.aqi} loading={mapLoading && !snap} />
                    </span>
                    <span className="watchlist-cat">{snap?.category || "Loading…"}</span>
                  </div>
                </button>
              ))}
            </div>
          )}
        </section>

        <section className="panel map-section reveal reveal-1">
          <div className="map-layout">
            <div>
              <div className="section-head">
                <div>
                  <p className="section-kicker">Overview</p>
                  <h2 className="section-title">Pakistan live map</h2>
                </div>
                <span className="section-icon">⌖</span>
              </div>
              <p className="section-sub">
                Current AQI across all monitored cities — click a marker to switch.
              </p>
              <AqiColorLegend compact />
              {mapLoading && !Object.keys(citySnapshots).length ? (
                <MapSkeleton />
              ) : (
                <PakistanMap
                  cities={
                    cities.length
                      ? cities
                      : [{ name: city, country: "Pakistan", lat: 31.52, lon: 74.36 }]
                  }
                  snapshots={citySnapshots}
                  activeCity={city}
                  onSelect={selectCity}
                  loading={mapLoading || mapRefreshing}
                />
              )}
            </div>
            <div>
              <div className="section-head">
                <div>
                  <p className="section-kicker">Compare</p>
                  <h2 className="section-title">City rankings</h2>
                </div>
              </div>
              <p className="section-sub">Sorted by current air quality — lower is healthier.</p>
              {mapLoading && !Object.keys(citySnapshots).length ? (
                <RankingsSkeleton />
              ) : (
                <>
                <div className="map-legend">
                  {rankedSnapshots.map(({ city: c, snap }) => (
        <button
                        key={c.name}
          type="button"
                        className={`map-legend-item ${c.name === city ? "active" : ""}`}
                        onClick={() => selectCity(c.name)}
                      >
                        <span
                          className="map-legend-dot"
                          style={{ background: snap?.color || "#94a3b8" }}
                        />
                        <span className="map-legend-name">{c.name}</span>
                        <span className="map-legend-aqi">
                          <AnimatedNumber value={snap?.aqi} loading={mapLoading && !snap} />
                        </span>
                        <span className="map-legend-cat muted">
                          {snap?.category?.split(" ")[0] || "…"}
                        </span>
        </button>
                    ))}
                </div>
                <div className="city-highlight-grid">
                  {cityHighlights.map((item) => (
                    <div className={`city-highlight-card tone-${item.tone}`} key={item.kicker}>
                      <p className="city-highlight-kicker">{item.kicker}</p>
                      <div className="city-highlight-row">
                        <strong>{item.city}</strong>
                        <span>{item.value != null ? Math.round(item.value) : "—"} AQI</span>
                      </div>
                      <p className="city-highlight-note">{item.note}</p>
                    </div>
                  ))}
                </div>
                </>
              )}
            </div>
          </div>
      </section>

        <section className={`hero reveal reveal-2 ${switching ? "is-city-switching" : ""}`}>
          <div className="panel panel-glow aqi-hero">
            <div className="panel-inner">
              <div className="aqi-hero-top">
                <div>
                  <p className="section-kicker">Current conditions</p>
                  <p className="city-display">
                    {city}
                    <span>Pakistan · live air quality</span>
                  </p>
                </div>
                <button
                  type="button"
                  className={`btn btn-watch ${watchlist.includes(city) ? "active" : ""}`}
                  onClick={() => toggleCity(city)}
                  disabled={!watchlist.includes(city) && watchlistFull}
                >
                  {watchlist.includes(city) ? "★ Saved" : "☆ Save city"}
                </button>
        </div>

              <div className="aqi-hero-center">
                <button
                  type="button"
                  className="aqi-explain-hit"
                  onClick={openExplainModal}
                  title="Explain this AQI number"
                  aria-label="Explain this AQI number"
                >
                  <AqiGauge value={forecast?.current_aqi} color={accentColor} loading={heroLoading} />
                </button>
                <div className="category-pill category-pill-hero">
                  <span
                    className="dot"
                    style={{ background: accentColor, color: accentColor }}
                  />
                  {heroLoading ? "Loading…" : forecast?.current_category || "—"}
        </div>
                <p className="aqi-hero-updated" title={updatedExact}>
                  Updated <strong>{heroLoading ? "…" : updatedRelative}</strong>
                  {!heroLoading && forecast?.event_time ? (
                    <span className="aqi-hero-date"> · {formatDayLabel(forecast.event_time)}</span>
                  ) : null}
                </p>
              </div>

              <div className="aqi-scale aqi-scale-hero">
                <div className="scale-bar">
                  <span
                    className="scale-marker"
                    style={{
                      left: `${scalePct}%`,
                      background: accentColor,
                      color: accentColor,
                    }}
                  />
                </div>
              </div>

              <AqiColorLegend bands activeCategory={forecast?.current_category} />

              <div className="weather-premium-shell">
                <div className="weather-premium-grid">
                  <div className="weather-premium-card">
                    <span className="weather-icon-badge" aria-hidden="true">
                      ◐
                    </span>
                    <div className="weather-premium-content">
                      <div className="weather-premium-top">
                        <span className="weather-metric-label">Temperature</span>
                      </div>
                      <strong>{weather?.temperature_c != null ? `${Math.round(weather.temperature_c)}°C` : "—"}</strong>
                      <small>{weather?.comfort_label || "live conditions"}</small>
                    </div>
                  </div>
                  <div className="weather-premium-card">
                    <span className="weather-icon-badge" aria-hidden="true">
                      ◍
                    </span>
                    <div className="weather-premium-content">
                      <div className="weather-premium-top">
                        <span className="weather-metric-label">Humidity</span>
                      </div>
                      <strong>{weather?.humidity_pct != null ? `${weather.humidity_pct}%` : "—"}</strong>
                      <small>{weather?.cloud_cover_pct != null ? `${weather.cloud_cover_pct}% cloud cover` : "air moisture"}</small>
                    </div>
                  </div>
                  <div className="weather-premium-card">
                    <span className="weather-icon-badge" aria-hidden="true">
                      ↗
                    </span>
                    <div className="weather-premium-content">
                      <div className="weather-premium-top">
                        <span className="weather-metric-label">Wind</span>
                      </div>
                      <strong>{weather?.wind_kph != null ? `${Math.round(weather.wind_kph)} km/h` : "—"}</strong>
                      <small>
                        {weather?.wind_label || "wind"} {weather?.wind_direction_deg != null ? `· ${formatWindDirection(weather.wind_direction_deg)}` : ""}
                      </small>
                    </div>
                  </div>
                </div>
              </div>

              <p className="city-conditions-summary">{cityConditionsSummary}</p>

              <div className="insight-ribbon-stack">
                {weather?.air_driver && (
                  <div className="insight-ribbon">
                    <span className="insight-ribbon-icon" aria-hidden="true">
                      ◈
                    </span>
                    <div>
                      <strong>Weather read</strong>
                      <p>{weather.air_driver}</p>
                    </div>
                  </div>
                )}
                {weather?.pollutant_driver_detail && (
                  <div className="insight-ribbon">
                    <span className="insight-ribbon-icon" aria-hidden="true">
                      ◎
                    </span>
                    <div>
                      <strong>{weather.pollutant_driver || "Pollutant"} driver</strong>
                      <p>{weather.pollutant_driver_detail}</p>
                    </div>
                  </div>
                )}
              </div>

              <div className="btn-row btn-row-center">
                <button
                  className="btn btn-primary"
                  type="button"
                  onClick={shareForecastPng}
                  disabled={!forecast || exporting}
                >
                  {exporting ? "Saving…" : "↓ Share PNG card"}
                </button>
                <button
                  className="btn"
                  type="button"
                  onClick={downloadForecastTxt}
                  disabled={!forecast}
                >
                  Export .txt
                </button>
              </div>
            </div>
          </div>

          <div className={`panel ${outlookLoading ? "is-section-loading" : ""}`}>
            <div className="section-head">
              <div>
                <p className="section-kicker">Outlook</p>
                <h2 className="section-title">Next 3 days</h2>
              </div>
              <span className="section-icon">◎</span>
            </div>
            <p className="section-sub">
              Expected air quality for the next 24, 48, and 72 hours
              {forecast?.event_time
                ? ` — ${formatHorizonDay(forecast.event_time, 24)} to ${formatHorizonDay(forecast.event_time, 72)}`
                : ""}
              , with likely ranges.
            </p>
            {outlookLoading && !forecast?.forecast?.length ? (
              <ChartSkeleton height={120} />
            ) : (
              <div className="forecast-mini-chart">
                <ResponsiveContainer width="100%" height={120}>
                  <ComposedChart data={forecastTrend} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
                    <CartesianGrid stroke="rgba(244,248,255,0.05)" vertical={false} />
                    <XAxis
                      dataKey="label"
                      stroke="#8b9db5"
                      tick={{ fontSize: 11 }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <YAxis
                      stroke="#8b9db5"
                      width={32}
                      tick={{ fontSize: 10 }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <Tooltip content={<ChartTooltip />} />
                    <Area
                      type="monotone"
                      dataKey="aqiLow"
                      stackId="confidence"
                      stroke="none"
                      fill="transparent"
                      name="Low"
                    />
                    <Area
                      type="monotone"
                      dataKey="aqiRange"
                      stackId="confidence"
                      stroke="none"
                      fill={accentColor}
                      fillOpacity={0.12}
                      name="Likely range"
                    />
                    <Line
                      type="monotone"
                      dataKey="aqi"
                      name="AQI"
                      stroke={accentColor}
                      strokeWidth={2.5}
                      dot={{ r: 4, fill: accentColor, stroke: "#fff", strokeWidth: 1.5 }}
                      activeDot={{ r: 6 }}
                    />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            )}
            <div className="forecast-insight-row">
              {peakInsight && (
                <div className={`forecast-insight tone-${peakInsight.tone}`}>
                  <p>{peakInsight.label}</p>
                  <strong>{peakInsight.value}</strong>
                  <span>{peakInsight.detail}</span>
                </div>
              )}
              {dropInsight && (
                <div className={`forecast-insight tone-${dropInsight.tone}`}>
                  <p>{dropInsight.label}</p>
                  <strong>{dropInsight.value}</strong>
                  <span>{dropInsight.detail}</span>
                </div>
              )}
              {confidenceInsight && (
                <div className={`forecast-insight tone-${confidenceInsight.tone}`}>
                  <p>Confidence</p>
                  <strong>{confidenceInsight.label}</strong>
                  <span>{confidenceInsight.detail}</span>
                </div>
              )}
            </div>
            <div className="forecast-strip">
              {(
                forecast?.forecast ??
                ([24, 48, 72].map((h) => ({
                  horizon_hours: h,
                  aqi: 0,
                  aqi_low: undefined,
                  aqi_high: undefined,
                  category: "—",
                  color: "#94a3b8",
                })) as ForecastResponse["forecast"])
              ).map((f) => (
                <div
                  className="forecast-card"
                  key={f.horizon_hours}
                  style={{ ["--card-accent" as string]: f.color || accentColor }}
                >
                  <div
                    className="horizon-dot"
                    style={{
                      background: f.color || accentColor,
                      boxShadow: `0 0 16px ${f.color || accentColor}`,
                    }}
                  />
                  <h3>+{f.horizon_hours}h</h3>
                  <p className="forecast-day">
                    {forecast?.event_time
                      ? formatHorizonDay(forecast.event_time, f.horizon_hours)
                      : "—"}
                  </p>
                  <p className="aqi-val" style={{ color: f.color || accentColor }}>
                    <AnimatedNumber value={f.aqi} loading={outlookLoading} />
                  </p>
                  {!outlookLoading && f.aqi_low != null && f.aqi_high != null && (
                    <p className="range">
                      {f.aqi_low} – {f.aqi_high}
                    </p>
                  )}
                  <span className="cat-label">{f.category}</span>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="grid-2 reveal reveal-3">
          <ExerciseCard data={exercise} error={insightError && !exercise ? "insights" : null} />
          <SmogSeasonPanel data={smogSeason} error={smogError && !smogSeason ? "smog" : null} />
        </section>

        <section className="grid-2 reveal reveal-3">
          <div className={`panel ${historyLoading ? "is-section-loading" : ""}`}>
            <div className="section-head">
              <div>
                <p className="section-kicker">History</p>
                <h2 className="section-title">Recent AQI trend</h2>
              </div>
              <span className="section-icon">↗</span>
            </div>
            <p className="section-sub">
              Last 7 days of hourly observations
              {historyChart.length
                ? ` — ${historyChart[0].time} to ${historyChart[historyChart.length - 1].time}`
                : ""}
              .
            </p>
            {historyLoading ? (
              <ChartSkeleton />
            ) : (
              <div className="chart-box">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={historyChart}>
                    <defs>
                      <linearGradient id="aqiFill" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor={accentColor} stopOpacity={0.5} />
                        <stop offset="100%" stopColor={accentColor} stopOpacity={0.02} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid stroke="rgba(244,248,255,0.05)" vertical={false} />
                    <XAxis dataKey="time" hide />
                    <YAxis stroke="#8b9db5" width={36} tick={{ fontSize: 11 }} axisLine={false} />
                    <Tooltip content={<ChartTooltip />} />
                    <Area
                      type="monotone"
                      dataKey="aqi"
                      name="AQI"
                      stroke={accentColor}
                      fill="url(#aqiFill)"
                      strokeWidth={2.5}
                      dot={false}
                      activeDot={{ r: 5, fill: accentColor, stroke: "#fff", strokeWidth: 2 }}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>

          <div className={`panel health-panel ${healthLoading ? "is-section-loading" : ""}`}>
            <div className="section-head">
              <div>
                <p className="section-kicker">Health</p>
                <h2 className="section-title">What to do now</h2>
              </div>
              <span className="section-icon">♥</span>
            </div>
            <p className="section-sub">Practical guidance for {city} based on current and forecast air quality.</p>

            {healthLoading ? (
              <div className="skeleton-block" style={{ minHeight: 160 }}>
                <div className="skeleton-line" style={{ width: "50%", marginBottom: 12 }} />
                <div className="skeleton-line" style={{ width: "90%", marginBottom: 8 }} />
                <div className="skeleton-line" style={{ width: "75%" }} />
              </div>
            ) : (
              <>
                {tips && (
                  <div
                    className={`health-now tip-level-${tips.current.level || "unknown"}`}
                    style={
                      {
                        ["--health-accent" as string]: accentColor,
                      } as CSSProperties
                    }
                  >
                    <p className="health-now-label">Do this now</p>
                    <strong className="health-now-title">{tips.current.title}</strong>
                    <p className="health-now-advice">{tips.current.advice}</p>
                    {!!tips.current.actions?.length && (
                      <div className="health-actions">
                        {tips.current.actions.map((action) => (
                          <div className="health-action" key={action.id} title={action.detail}>
                            <span className="health-action-icon" aria-hidden="true">
                              {action.id === "outdoor"
                                ? "◎"
                                : action.id === "mask"
                                  ? "▣"
                                  : action.id === "windows"
                                    ? "◫"
                                    : action.id === "sensitive"
                                      ? "♡"
                                      : "•"}
                            </span>
                            <span className="health-action-text">
                              <strong>{action.label}</strong>
                              <span>{action.detail}</span>
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {!!tips?.forecast_tips?.length && (
                  <div className="health-ahead">
                    <p className="health-ahead-label">Watch ahead</p>
                    <div className="health-ahead-grid">
                      {tips.forecast_tips.map((ft) => (
                        <div
                          className={`health-ahead-card tip-level-${ft.level || "unknown"}`}
                          key={ft.horizon_hours}
                        >
                          <span className="health-ahead-horizon">+{ft.horizon_hours}h</span>
                          <span className="health-ahead-date">
                            {forecast?.event_time
                              ? formatHorizonDay(forecast.event_time, ft.horizon_hours)
                              : "—"}
                          </span>
                          <strong>{ft.category}</strong>
                          <p>{ft.advice}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div className="health-alerts-block">
                  <p className="health-ahead-label">Alerts</p>
                  {!alerts.length && !healthLoading && (
                    <div className="alert-clear">
                      <span className="alert-clear-icon" aria-hidden="true">
                        ✓
                      </span>
                      <div>
                        <strong>All clear</strong>
                        <p>No unhealthy levels in the 3-day outlook — keep an eye on Watch ahead.</p>
                      </div>
                    </div>
                  )}
                  {alerts.map((a) => {
                    const level =
                      a.category === "Hazardous"
                        ? "hazard"
                        : a.category === "Very Unhealthy"
                          ? "very"
                          : a.category === "Unhealthy"
                            ? "unhealthy"
                            : a.category.includes("Sensitive")
                              ? "sensitive"
                              : "unhealthy";
                    const hours = parseHorizonHours(a.when);
                    const whenLabel =
                      a.when === "current"
                        ? `Now · ${formatDayLabel(forecast?.event_time)}`
                        : hours != null
                          ? `${a.when} · ${formatHorizonDay(forecast?.event_time, hours)}`
                          : a.when;
                    return (
                      <div className={`alert-card alert-${level}`} key={`${a.when}-${a.aqi}`}>
                        <div className="alert-card-top">
                          <span className="alert-when">{whenLabel}</span>
                          <span className="alert-cat">{a.category}</span>
                        </div>
                        <div className="alert-card-body">
                          <p className="alert-aqi">
                            <span>{a.aqi}</span>
                            <small>AQI</small>
                          </p>
                          <p className="alert-message">{a.message}</p>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </>
            )}
        </div>
      </section>

        <div className="mode-hint panel">
          <p>
            Curious how the forecasts are made?{" "}
            <button type="button" className="link-btn" onClick={() => setMode("technical")}>
              Switch to For experts
            </button>{" "}
            for models, explainability, and live accuracy.
          </p>
        </div>
          </>
        )}

        {isTechnical && (
          <>
        <div className="ops-strip reveal reveal-2">
          <span className="ops-pill">
            <span className="ops-icon">◈</span>
            Storage <strong>{ops?.storage_mode || "—"}</strong>
          </span>
          <button
            type="button"
            className={`ops-pill ops-pill-btn ${opsOpen ? "open" : ""}`}
            title={modelFull || "Model"}
            onClick={() => setOpsOpen((v) => !v)}
            aria-expanded={opsOpen}
          >
            <span className="ops-icon">◆</span>
            Model <strong>{shortModelLabel(modelFull)}</strong>
          </button>
          <span className="ops-pill">
            <span className="ops-icon">◷</span>
            Trained{" "}
            <strong>
              {ops?.last_train_at ? new Date(ops.last_train_at).toLocaleDateString() : "—"}
            </strong>
          </span>
          <span className="ops-pill">
            <span className="ops-icon">↻</span>
            Sync{" "}
            <strong>
              {ops?.features_updated_at
                ? new Date(ops.features_updated_at * 1000).toLocaleDateString()
                : "—"}
            </strong>
          </span>
          {opsOpen && modelFull && (
            <div className="ops-model-detail" title={modelFull}>
              {formatModelName(modelFull)}
            </div>
          )}
        </div>

        <section className="grid-2 reveal reveal-2">
          <BaselinePanel data={baseline} />
          <PipelinePanel data={pipeline} />
        </section>

        <section className="grid-2 reveal reveal-3">
          <div className="panel">
            <div className="section-head">
              <div>
                <p className="section-kicker">Models</p>
                <h2 className="section-title">Leaderboard</h2>
              </div>
              <span className="section-icon">★</span>
            </div>
            {!leaderboard.models.length && (
              <div className="empty-state">Train models to populate the leaderboard.</div>
            )}
            {!!leaderboard.models.length && (
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Model</th>
                      <th>RMSE</th>
                      <th>MAE</th>
                      <th>R²</th>
                      <th>Band</th>
                    </tr>
                  </thead>
                  <tbody>
                    {leaderboard.models.map((m) => {
                      const isBest = m.name === bestModelName;
                      const cat = m.val.overall.category_accuracy;
                      return (
                        <tr key={m.name} className={isBest ? "winner-row" : undefined}>
                          <td>
                            {m.name.replace(/_/g, " ")}
                            {isBest ? " ★" : ""}
                          </td>
                          <td>{m.val.overall.rmse.toFixed(1)}</td>
                          <td>{m.val.overall.mae.toFixed(1)}</td>
                          <td>{m.val.overall.r2.toFixed(3)}</td>
                          <td>
                            {cat == null || Number.isNaN(cat) ? "—" : `${(cat * 100).toFixed(0)}%`}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <div className="panel">
            <div className="section-head">
              <div>
                <p className="section-kicker">Explainability</p>
                <h2 className="section-title">XAI · {city}</h2>
              </div>
              <span className="section-icon">◉</span>
            </div>
            <p className="section-sub">
              {explainMeta.note || "What drives the forecast for this city."}
            </p>
            {!shap.length && !techLoading && (
              <div className="empty-state">Explanation appears after training completes.</div>
            )}
            {techLoading && !shapChart.length && <ChartSkeleton height={220} />}
            {!!shapChart.length && (
              <>
                <p className="chart-subtitle">City-level drivers</p>
                <div className="chart-box" style={{ height: 220 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={shapChart} layout="vertical" margin={{ left: 8, right: 12 }}>
                      <CartesianGrid stroke="rgba(244,248,255,0.05)" horizontal={false} />
                      <XAxis type="number" stroke="#8b9db5" tick={{ fontSize: 10 }} />
                      <YAxis
                        type="category"
                        dataKey="feature"
                        width={108}
                        stroke="#8b9db5"
                        tick={{ fontSize: 10 }}
                      />
                      <Tooltip content={<ChartTooltip />} />
                      <Bar
                        dataKey="importance"
                        name="Importance"
                        fill="#ff8c42"
                        radius={[0, 6, 6, 0]}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
                {!!localShapChart.length && (
                  <>
                    <p className="chart-subtitle">Latest hour (local)</p>
                    <div className="chart-box" style={{ height: 220 }}>
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart
                          data={localShapChart}
                          layout="vertical"
                          margin={{ left: 8, right: 12 }}
                        >
                          <CartesianGrid stroke="rgba(244,248,255,0.05)" horizontal={false} />
                          <XAxis type="number" stroke="#8b9db5" tick={{ fontSize: 10 }} />
                          <YAxis
                            type="category"
                            dataKey="feature"
                            width={108}
                            stroke="#8b9db5"
                            tick={{ fontSize: 10 }}
                          />
                          <Tooltip content={<ChartTooltip />} />
                          <Bar
                            dataKey="importance"
                            name="Importance"
                            fill={accentColor}
                            radius={[0, 6, 6, 0]}
                          />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  </>
                )}
              </>
            )}
        </div>
      </section>

        <section className="panel section-panel reveal reveal-6">
          <div className="section-head">
            <div>
              <p className="section-kicker">Operations</p>
              <h2 className="section-title">Live accuracy</h2>
            </div>
            <span className="section-icon">◈</span>
          </div>
          <p className="section-sub">
            Forecast vs observed AQI once each horizon matures — real-world tracking.
          </p>
          {!monitoring?.scored_rows ? (
            <div className="empty-state">Run the monitoring pipeline to seed scored history.</div>
          ) : (
            <>
              <div className="stat-row">
                <div className="stat-card">
                  <p className="stat-label">Scored</p>
                  <p className="stat-value">
                    <AnimatedNumber value={monitoring.scored_rows} />
                  </p>
                  <span className="stat-hint">{monitoring.pending_rows ?? 0} pending</span>
                </div>
                <div className="stat-card">
                  <p className="stat-label">MAE</p>
                  <p className="stat-value">
                    <AnimatedNumber value={maeDisplay ?? undefined} decimals={1} />
                  </p>
                  <span className="stat-hint">{city}</span>
                </div>
                <div className="stat-card">
                  <p className="stat-label">Band accuracy</p>
                  <p className="stat-value">
                    {catAcc == null ? (
                      "—"
                    ) : (
                      <>
                        <AnimatedNumber value={catAcc * 100} decimals={0} />%
                      </>
                    )}
                  </p>
                  <span className="stat-hint">category match</span>
                </div>
              </div>
              {!!monitoring.recent?.length && (
                <div className="table-wrap" style={{ marginTop: "1.35rem" }}>
                  <table className="table">
                    <thead>
                      <tr>
                        <th>City</th>
                        <th>Horizon</th>
                        <th>Pred</th>
                        <th>Actual</th>
                        <th>Error</th>
                        <th>Band</th>
                      </tr>
                    </thead>
                    <tbody>
                      {monitoring.recent.slice(0, 10).map((r) => (
                        <tr key={`${r.city}-${r.target_time}-${r.horizon_hours}`}>
                          <td>{r.city}</td>
                          <td>
                            +{r.horizon_hours}h
                            <div className="muted" style={{ fontSize: "0.75rem" }}>
                              {formatDayLabel(r.target_time)}
                            </div>
                          </td>
                          <td>{r.predicted_aqi}</td>
                          <td>{r.actual_aqi}</td>
                          <td>{r.abs_error}</td>
                          <td>
                            <span
                              className={`badge ${r.category_hit ? "badge-hit" : "badge-miss"}`}
                            >
                              {r.category_hit ? "hit" : "miss"}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </section>
          </>
        )}

        <footer className="app-footer">
          <div className="footer-brand">
            <div className="brand-mark" style={{ color: accentColor, width: 36, height: 36 }}>
              <BrandMark />
            </div>
            <strong>{BRAND.name}</strong>
          </div>
          <p className="footer-meta">
            {isEveryday
              ? "Air quality forecasts for 5 Pakistan cities"
              : "MLOps · Hopsworks · GitHub Actions · Explainable AI"}
            <br />
            {isEveryday ? (
              <button type="button" className="link-btn" onClick={() => setMode("technical")}>
                For experts
              </button>
            ) : (
              <button type="button" className="link-btn" onClick={() => setMode("everyday")}>
                Back to For you
              </button>
            )}
          </p>
        </footer>
      </div>

      <ExplainAqiModal
        open={explainOpen}
        data={explainAqi}
        onClose={closeExplainModal}
      />
    </>
  );
}

export default App;
