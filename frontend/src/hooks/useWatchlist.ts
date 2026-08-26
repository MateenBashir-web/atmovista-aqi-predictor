import { useEffect, useState } from "react";

const STORAGE_KEY = "atmovista-watchlist";
const MAX_ITEMS = 4;

function getInitialWatchlist(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((item): item is string => typeof item === "string").slice(0, MAX_ITEMS);
  } catch {
    return [];
  }
}

export function useWatchlist() {
  const [watchlist, setWatchlist] = useState<string[]>(getInitialWatchlist);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(watchlist));
  }, [watchlist]);

  const toggleCity = (city: string) => {
    setWatchlist((prev) => {
      if (prev.includes(city)) return prev.filter((item) => item !== city);
      return [...prev, city].slice(-MAX_ITEMS);
    });
  };

  return { watchlist, toggleCity, maxWatchlistItems: MAX_ITEMS };
}
