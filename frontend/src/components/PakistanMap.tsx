import type { City } from "../api";
import {
  buildPakistanPath,
  CITY_MARKER_LAYOUT,
  CITY_REFERENCE,
  MAP_VIEWBOX,
  projectLonLat,
} from "./pakistanGeo";

export type CitySnapshot = {
  name: string;
  aqi: number | null;
  category: string;
  color: string;
  lat: number;
  lon: number;
};

type Props = {
  cities: City[];
  snapshots: Record<string, CitySnapshot>;
  activeCity: string;
  onSelect: (name: string) => void;
  loading?: boolean;
};

export function PakistanMap({ cities, snapshots, activeCity, onSelect, loading }: Props) {
  const pakistanPath = buildPakistanPath();

  return (
    <div className="pak-map-wrap">
      <svg
        viewBox={MAP_VIEWBOX}
        className="pak-map-svg"
        role="img"
        aria-label="Pakistan air quality map"
      >
        <defs>
          <linearGradient id="mapFill" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="var(--map-fill-a)" />
            <stop offset="100%" stopColor="var(--map-fill-b)" />
          </linearGradient>
          <filter id="mapGlow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        <path className="pak-outline" d={pakistanPath} fill="url(#mapFill)" />
        <path className="pak-border" d={pakistanPath} fill="none" />

        {cities.map((c) => {
          const snap = snapshots[c.name];
          const { x, y } = projectLonLat(c.lon, c.lat);
          const isActive = c.name === activeCity;
          const color = snap?.color || "#94a3b8";
          const aqi = snap?.aqi;
          const ref = CITY_REFERENCE[c.name];
          const layout = CITY_MARKER_LAYOUT[c.name] ?? {
            labelDx: 0,
            labelDy: 34,
            anchor: "middle" as const,
          };

          return (
            <g key={c.name} transform={`translate(${x}, ${y})`}>
              <g
                className={`map-marker ${isActive ? "active" : ""} ${loading && !snap ? "loading" : ""}`}
                onClick={() => onSelect(c.name)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onSelect(c.name);
                  }
                }}
                role="button"
                tabIndex={0}
                aria-label={`${c.name}, ${ref?.region ?? "Pakistan"}, AQI ${aqi ?? "loading"}`}
                aria-pressed={isActive}
              >
                <title>{`${c.name} (${ref?.region ?? "Pakistan"}) — AQI ${aqi ?? "…"}`}</title>
                <circle className="map-marker-hit" r="18" fill="transparent" />
                {isActive && (
                  <circle
                    className="map-marker-ring"
                    r="15"
                    fill="none"
                    stroke={color}
                    strokeWidth="1.5"
                  />
                )}
                <circle
                  className="map-marker-dot"
                  r={isActive ? 9 : 8}
                  fill={color}
                  filter="url(#mapGlow)"
                />
                <text
                  className={`map-marker-aqi ${aqi != null && Math.round(aqi) >= 100 ? "aqi-3dig" : ""}`}
                  y="3.2"
                  textAnchor="middle"
                  pointerEvents="none"
                >
                  {aqi != null ? Math.round(aqi) : "·"}
                </text>
              </g>
              <text
                className={`map-marker-label ${isActive ? "active" : ""}`}
                x={layout.labelDx}
                y={layout.labelDy}
                textAnchor={layout.anchor}
                pointerEvents="none"
              >
                {c.name}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
