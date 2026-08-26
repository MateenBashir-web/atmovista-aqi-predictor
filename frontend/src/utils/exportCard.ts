import { BRAND } from "../brand";
import type { ForecastResponse } from "../api";

function roundRect(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  r: number,
) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

export async function exportForecastPng(forecast: ForecastResponse): Promise<void> {
  const W = 900;
  const H = 560;
  const canvas = document.createElement("canvas");
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;

  const accent = forecast.current_color || "#3ecfb2";

  const bg = ctx.createLinearGradient(0, 0, W, H);
  bg.addColorStop(0, "#030810");
  bg.addColorStop(0.45, "#071422");
  bg.addColorStop(1, "#0c1a2e");
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, W, H);

  const glow = ctx.createRadialGradient(180, 160, 20, 180, 160, 280);
  glow.addColorStop(0, `${accent}55`);
  glow.addColorStop(1, "transparent");
  ctx.fillStyle = glow;
  ctx.fillRect(0, 0, W, H);

  ctx.fillStyle = "#f4f8ff";
  ctx.font = "700 42px Fraunces, Georgia, serif";
  ctx.fillText(BRAND.name, 48, 70);

  ctx.fillStyle = "#8b9db5";
  ctx.font = "500 18px Sora, sans-serif";
  ctx.fillText(BRAND.tagline, 48, 102);

  ctx.fillStyle = "#f4f8ff";
  ctx.font = "600 28px Sora, sans-serif";
  ctx.fillText(`${forecast.city}, Pakistan`, 48, 170);

  ctx.fillStyle = accent;
  ctx.font = "700 120px Fraunces, Georgia, serif";
  ctx.fillText(String(forecast.current_aqi ?? "—"), 48, 300);

  ctx.fillStyle = "#f4f8ff";
  ctx.font = "600 22px Sora, sans-serif";
  ctx.fillText(forecast.current_category || "—", 48, 340);

  const cards = forecast.forecast.slice(0, 3);
  const cardW = 240;
  const gap = 20;
  const startX = 48;
  cards.forEach((f, i) => {
    const x = startX + i * (cardW + gap);
    const y = 380;
    ctx.fillStyle = "rgba(255,255,255,0.04)";
    roundRect(ctx, x, y, cardW, 120, 16);
    ctx.fill();
    ctx.strokeStyle = "rgba(244,248,255,0.12)";
    ctx.lineWidth = 1;
    ctx.stroke();

    ctx.fillStyle = f.color || accent;
    ctx.fillRect(x, y, cardW, 4);

    ctx.fillStyle = "#8b9db5";
    ctx.font = "600 14px Sora, sans-serif";
    ctx.fillText(`+${f.horizon_hours}h`, x + 18, y + 28);
    const day = new Date(new Date(forecast.event_time).getTime() + f.horizon_hours * 3600000);
    ctx.font = "500 12px Sora, sans-serif";
    ctx.fillText(
      day.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" }),
      x + 18,
      y + 46,
    );

    ctx.fillStyle = f.color || accent;
    ctx.font = "700 32px Fraunces, Georgia, serif";
    ctx.fillText(String(f.aqi), x + 18, y + 82);

    ctx.fillStyle = "#8b9db5";
    ctx.font = "500 12px Sora, sans-serif";
    ctx.fillText(f.category, x + 18, y + 104);
  });

  ctx.fillStyle = "#8b9db5";
  ctx.font = "500 13px Sora, sans-serif";
  ctx.fillText(`Updated ${new Date(forecast.event_time).toLocaleString()}`, 48, H - 28);

  await new Promise<void>((resolve) => {
    canvas.toBlob((blob) => {
      if (!blob) {
        resolve();
        return;
      }
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `atmovista-${forecast.city.toLowerCase()}-forecast.png`;
      a.click();
      URL.revokeObjectURL(url);
      resolve();
    }, "image/png");
  });
}
