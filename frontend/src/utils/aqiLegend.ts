export const AQI_LEGEND = [
  { label: "Good", range: "0–50", color: "#22c55e" },
  { label: "Moderate", range: "51–100", color: "#eab308" },
  { label: "Sensitive", range: "101–150", color: "#f97316" },
  { label: "Unhealthy", range: "151–200", color: "#ef4444" },
  { label: "Very Unhealthy", range: "201–300", color: "#a855f7" },
  { label: "Hazardous", range: "301+", color: "#fb7185" },
] as const;
