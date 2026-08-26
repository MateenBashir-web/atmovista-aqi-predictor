import { useCallback, useEffect, useState } from "react";
import { api, type City } from "../api";
import type { CitySnapshot } from "../components/PakistanMap";
import { rememberForecast } from "../utils/requestCache";

function toSnapshot(city: City, row: {
  current_aqi: number | null;
  current_category: string;
  current_color: string;
}): CitySnapshot {
  return {
    name: city.name,
    aqi: row.current_aqi,
    category: row.current_category,
    color: row.current_color,
    lat: city.lat,
    lon: city.lon,
  };
}

export function useCitySnapshots(cities: City[], priorityCity?: string) {
  const [snapshots, setSnapshots] = useState<Record<string, CitySnapshot>>({});
  const [loading, setLoading] = useState(true);
  const [loadedCount, setLoadedCount] = useState(0);

  const applyRows = useCallback(
    (rows: Record<string, { current_aqi: number | null; current_category: string; current_color: string }>) => {
      setSnapshots((prev) => {
        const next = { ...prev };
        for (const city of cities) {
          const row = rows[city.name];
          if (row) next[city.name] = toSnapshot(city, row);
        }
        return next;
      });
      setLoadedCount(Object.keys(rows).length);
    },
    [cities],
  );

  useEffect(() => {
    if (!cities.length) return;

    let cancelled = false;
    setLoading(true);

    const loadPriority = async () => {
      if (!priorityCity) return;
      const city = cities.find((c) => c.name === priorityCity);
      if (!city) return;
      try {
        const forecast = await api.forecast(priorityCity);
        if (cancelled) return;
        rememberForecast(priorityCity, forecast);
        setSnapshots((prev) => ({
          ...prev,
          [priorityCity]: toSnapshot(city, forecast),
        }));
        setLoadedCount((n) => Math.max(n, 1));
      } catch {

      }
    };

    const loadBatch = async () => {
      try {
        const res = await api.snapshots();
        if (cancelled) return;
        applyRows(res.snapshots);
      } catch {
        if (!cancelled) setLoadedCount(0);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    void loadPriority().finally(() => {
      if (!cancelled) void loadBatch();
    });

    const intervalId = window.setInterval(() => {
      void api.snapshots().then((res) => applyRows(res.snapshots)).catch(() => undefined);
    }, 5 * 60 * 1000);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [cities, priorityCity, applyRows]);

  const patchSnapshot = useCallback((name: string, snap: CitySnapshot) => {
    setSnapshots((prev) => {
      const existing = prev[name];
      if (
        existing &&
        existing.aqi === snap.aqi &&
        existing.category === snap.category &&
        existing.color === snap.color
      ) {
        return prev;
      }
      return { ...prev, [name]: snap };
    });
  }, []);

  return {
    snapshots,
    mapLoading: loading && loadedCount === 0,
    mapRefreshing: loading && loadedCount > 0,
    patchSnapshot,
  };
}
