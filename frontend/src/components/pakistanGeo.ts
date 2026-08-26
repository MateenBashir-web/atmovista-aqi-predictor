
export const MAP_BOUNDS = {
  lonMin: 60.8,
  lonMax: 77.8,
  latMin: 23.5,
  latMax: 37.2,
} as const;

const SVG = { padX: 52, padY: 36, width: 180, height: 250 };

export const PAKISTAN_BORDER: [number, number][] = [
  [60.87, 24.05],
  [61.62, 24.83],
  [62.78, 25.18],
  [64.59, 25.22],
  [66.65, 25.29],
  [67.04, 24.87],
  [67.73, 24.87],
  [68.54, 25.83],
  [69.42, 26.74],
  [70.28, 27.71],
  [70.42, 28.07],
  [70.01, 28.79],
  [70.64, 29.09],
  [71.06, 29.64],
  [71.58, 29.78],
  [72.56, 29.22],
  [73.52, 29.78],
  [74.06, 30.4],
  [74.82, 31.54],
  [75.06, 32.15],
  [74.8, 32.83],
  [75.06, 33.23],
  [74.63, 33.91],
  [74.55, 34.72],
  [73.63, 34.79],
  [72.61, 35.2],
  [71.85, 35.65],
  [71.43, 36.07],
  [71.08, 36.49],
  [72.26, 36.95],
  [73.73, 36.91],
  [74.88, 36.99],
  [75.82, 36.92],
  [76.19, 36.69],
  [77.0, 35.49],
  [77.84, 35.49],
  [76.87, 34.79],
  [76.13, 33.96],
  [75.4, 32.54],
  [74.21, 31.77],
  [73.05, 31.17],
  [71.18, 30.18],
  [70.07, 28.99],
  [68.18, 27.73],
  [66.72, 26.49],
  [64.53, 25.75],
  [62.55, 25.08],
  [61.17, 25.2],
  [60.87, 24.05],
];

export function projectLonLat(lon: number, lat: number): { x: number; y: number } {
  const { lonMin, lonMax, latMin, latMax } = MAP_BOUNDS;
  const x = SVG.padX + ((lon - lonMin) / (lonMax - lonMin)) * SVG.width;
  const y = SVG.padY + ((latMax - lat) / (latMax - latMin)) * SVG.height;
  return { x, y };
}

export function buildPakistanPath(): string {
  return PAKISTAN_BORDER.map(([lon, lat], i) => {
    const { x, y } = projectLonLat(lon, lat);
    return `${i === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`;
  }).join(" ");
}

export const CITY_MARKER_LAYOUT: Record<
  string,
  { labelDx: number; labelDy: number; anchor: "start" | "middle" | "end"; leader?: boolean }
> = {
  Karachi: { labelDx: 0, labelDy: 15, anchor: "middle" },
  Quetta: { labelDx: -11, labelDy: 3, anchor: "end" },
  Lahore: { labelDx: -11, labelDy: 9, anchor: "end" },
  Islamabad: { labelDx: 11, labelDy: 3, anchor: "start" },
  Peshawar: { labelDx: -11, labelDy: -3, anchor: "end" },
};

export const MAP_VIEWBOX = `0 0 ${SVG.padX * 2 + SVG.width} ${SVG.padY * 2 + SVG.height}`;

export const CITY_REFERENCE: Record<string, { lat: number; lon: number; region: string }> = {
  Karachi: { lat: 24.8607, lon: 67.0011, region: "Sindh · south coast" },
  Quetta: { lat: 30.1798, lon: 66.975, region: "Balochistan · southwest" },
  Lahore: { lat: 31.5204, lon: 74.3587, region: "Punjab · east" },
  Islamabad: { lat: 33.6844, lon: 73.0479, region: "Capital · north-central" },
  Peshawar: { lat: 34.0151, lon: 71.5249, region: "KPK · northwest" },
};
