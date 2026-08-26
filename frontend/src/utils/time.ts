export function formatRelativeTime(isoOrDate: string | Date | null | undefined): string {
  if (!isoOrDate) return "—";
  const date = typeof isoOrDate === "string" ? new Date(isoOrDate) : isoOrDate;
  if (Number.isNaN(date.getTime())) return "—";

  const seconds = Math.round((Date.now() - date.getTime()) / 1000);
  if (seconds < 10) return "just now";
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function addHours(isoOrDate: string | Date | null | undefined, hours: number): Date | null {
  if (!isoOrDate) return null;
  const base = typeof isoOrDate === "string" ? new Date(isoOrDate) : isoOrDate;
  if (Number.isNaN(base.getTime())) return null;
  return new Date(base.getTime() + hours * 60 * 60 * 1000);
}

export function formatDayLabel(isoOrDate: string | Date | null | undefined): string {
  if (!isoOrDate) return "—";
  const date = typeof isoOrDate === "string" ? new Date(isoOrDate) : isoOrDate;
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleDateString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
  });
}

export function formatChartDay(isoOrDate: string | Date | null | undefined): string {
  if (!isoOrDate) return "—";
  const date = typeof isoOrDate === "string" ? new Date(isoOrDate) : isoOrDate;
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

export function formatHorizonDay(
  baseEventTime: string | Date | null | undefined,
  horizonHours: number,
): string {
  return formatDayLabel(addHours(baseEventTime, horizonHours));
}

export function formatHorizonChartLabel(
  baseEventTime: string | Date | null | undefined,
  horizonHours: number,
): string {
  return formatChartDay(addHours(baseEventTime, horizonHours));
}

export function parseHorizonHours(when: string): number | null {
  const match = when.match(/^\+(\d+)h$/i);
  if (!match) return null;
  return Number(match[1]);
}
