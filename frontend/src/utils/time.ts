/** Pakistan-facing app: show calendar dates/times in local time. */
export const APP_TIMEZONE = "Asia/Karachi";

const DATE_FMT: Intl.DateTimeFormatOptions = {
  timeZone: APP_TIMEZONE,
  weekday: "short",
  month: "short",
  day: "numeric",
};

const CHART_DATE_FMT: Intl.DateTimeFormatOptions = {
  timeZone: APP_TIMEZONE,
  month: "short",
  day: "numeric",
};

const DATETIME_FMT: Intl.DateTimeFormatOptions = {
  timeZone: APP_TIMEZONE,
  dateStyle: "medium",
  timeStyle: "short",
};

export function parseAppDate(isoOrDate: string | Date | null | undefined): Date | null {
  if (!isoOrDate) return null;
  if (isoOrDate instanceof Date) {
    return Number.isNaN(isoOrDate.getTime()) ? null : isoOrDate;
  }
  const normalized = isoOrDate.trim().replace(" ", "T");
  const date = new Date(normalized);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function formatRelativeTime(isoOrDate: string | Date | null | undefined): string {
  const date = parseAppDate(isoOrDate);
  if (!date) return "—";

  const seconds = Math.round((Date.now() - date.getTime()) / 1000);
  if (seconds < 10) return "just now";
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return date.toLocaleDateString("en-PK", CHART_DATE_FMT);
}

export function addHours(isoOrDate: string | Date | null | undefined, hours: number): Date | null {
  const base = parseAppDate(isoOrDate);
  if (!base) return null;
  return new Date(base.getTime() + hours * 60 * 60 * 1000);
}

export function formatDayLabel(isoOrDate: string | Date | null | undefined): string {
  const date = parseAppDate(isoOrDate);
  if (!date) return "—";
  return date.toLocaleDateString("en-PK", DATE_FMT);
}

export function formatDateTime(isoOrDate: string | Date | null | undefined): string {
  const date = parseAppDate(isoOrDate);
  if (!date) return "—";
  return date.toLocaleString("en-PK", DATETIME_FMT);
}

export function formatChartDay(isoOrDate: string | Date | null | undefined): string {
  const date = parseAppDate(isoOrDate);
  if (!date) return "—";
  return date.toLocaleDateString("en-PK", CHART_DATE_FMT);
}

export function formatChartDateTime(isoOrDate: string | Date | null | undefined): string {
  const date = parseAppDate(isoOrDate);
  if (!date) return "—";
  return date.toLocaleString("en-PK", {
    timeZone: APP_TIMEZONE,
    month: "short",
    day: "numeric",
    hour: "2-digit",
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
