import type { ForecastResponse } from "../api";

const forecastCache = new Map<string, ForecastResponse>();
const forecastInflight = new Map<string, Promise<ForecastResponse>>();

export function getCachedForecast(city: string): ForecastResponse | undefined {
  return forecastCache.get(city);
}

export function rememberForecast(city: string, data: ForecastResponse) {
  forecastCache.set(city, data);
}

export async function fetchForecastDeduped(
  fetcher: (city: string) => Promise<ForecastResponse>,
  city: string,
): Promise<ForecastResponse> {
  const cached = forecastCache.get(city);
  if (cached) return cached;

  const pending = forecastInflight.get(city);
  if (pending) return pending;

  const promise = fetcher(city)
    .then((data) => {
      forecastCache.set(city, data);
      forecastInflight.delete(city);
      return data;
    })
    .catch((err) => {
      forecastInflight.delete(city);
      throw err;
    });

  forecastInflight.set(city, promise);
  return promise;
}
