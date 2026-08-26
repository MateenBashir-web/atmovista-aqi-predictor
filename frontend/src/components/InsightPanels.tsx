import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import type { BaselineResponse, ExerciseResponse, PipelineResponse, SmogSeasonResponse } from "../api";
import type { ExplainAqiResponse } from "../api";

export function SmogSeasonPanel({
  data,
  error,
}: {
  data: SmogSeasonResponse | null;
  error?: string | null;
}) {
  if (error) {
    return (
      <div className="panel insight-panel">
        <div className="empty-state">Couldn’t load smog season. Restart the API, then refresh.</div>
      </div>
    );
  }
  if (!data) {
    return (
      <div className="panel insight-panel">
        <div className="empty-state">Loading smog season…</div>
      </div>
    );
  }
  const maxAqi = Math.max(...data.months.map((m) => m.mean_aqi), 1);

  return (
    <div className="panel insight-panel">
      <div className="section-head">
        <div>
          <p className="section-kicker">Pakistan context</p>
          <h2 className="section-title">Smog season</h2>
        </div>
        <span className="section-icon">☁</span>
      </div>
      <p className="section-sub">{data.headline}</p>
      <p className="insight-summary">{data.summary}</p>
      <div className="smog-months">
        {data.months.map((m) => (
          <div
            key={m.month}
            className={`smog-month ${m.is_peak_smog ? "peak" : ""} ${m.is_current ? "current" : ""}`}
            title={`${m.label}: ~${m.mean_aqi} AQI (${m.category})`}
          >
            <div className="smog-bar-wrap">
              <div
                className="smog-bar"
                style={{
                  height: `${Math.max(12, (m.mean_aqi / maxAqi) * 100)}%`,
                  background: m.color,
                }}
              />
            </div>
            <span className="smog-label">{m.label}</span>
          </div>
        ))}
      </div>
      <p className="smog-legend muted">
        Highlighted months = peak smog window ({data.peak_smog_label}). Bars = mean AQI from 1-year
        training data.
      </p>
    </div>
  );
}

export function ExerciseCard({
  data,
  error,
}: {
  data: ExerciseResponse | null;
  error?: string | null;
}) {
  if (error) {
    return (
      <div className="panel insight-panel">
        <div className="empty-state">Couldn’t load exercise advice. Restart the API, then refresh.</div>
      </div>
    );
  }
  if (!data) {
    return (
      <div className="panel insight-panel">
        <div className="empty-state">Loading exercise advice…</div>
      </div>
    );
  }

  return (
    <div className={`panel insight-panel exercise-card verdict-${data.verdict}`}>
      <div className="section-head">
        <div>
          <p className="section-kicker">Decision</p>
          <h2 className="section-title">Should I exercise?</h2>
        </div>
        <span className={`exercise-badge verdict-${data.verdict}`}>
          {data.verdict === "yes" ? "YES" : data.verdict === "caution" ? "CAUTION" : data.verdict === "no" ? "NO" : "…"}
        </span>
      </div>
      <p className="exercise-title">{data.title}</p>
      <p className="insight-summary">{data.reason}</p>
      <p className="exercise-rec">{data.recommendation}</p>
    </div>
  );
}

export function ExplainAqiModal({
  open,
  data,
  onClose,
}: {
  open: boolean;
  data: ExplainAqiResponse | null;
  onClose: () => void;
}) {
  const [mounted, setMounted] = useState(open);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (open) {
      setMounted(true);
      const frame = requestAnimationFrame(() => {
        requestAnimationFrame(() => setVisible(true));
      });
      const prevOverflow = document.body.style.overflow;
      document.body.style.overflow = "hidden";
      return () => {
        cancelAnimationFrame(frame);
        document.body.style.overflow = prevOverflow;
      };
    }

    setVisible(false);
    const timer = window.setTimeout(() => setMounted(false), 340);
    return () => window.clearTimeout(timer);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!mounted) return null;

  return createPortal(
    <div
      className={`modal-backdrop ${visible ? "is-visible" : ""}`}
      role="presentation"
      onClick={onClose}
    >
      <div
        className="modal-card"
        role="dialog"
        aria-modal="true"
        aria-label="Explain this AQI"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-head">
          <div>
            <p className="section-kicker">Explain this number</p>
            <h2 className="section-title">{data?.headline || "Air quality"}</h2>
          </div>
          <button type="button" className="btn" onClick={onClose}>
            Close
          </button>
        </div>
        {data ? (
          <>
            <div className="explain-aqi-hero" style={{ color: data.color }}>
              <span className="explain-aqi-num">{data.aqi ?? "—"}</span>
              <span className="explain-aqi-cat">{data.category}</span>
              {data.band && (
                <span className="explain-aqi-range muted">
                  Band {data.band.min}–{data.band.max}
                </span>
              )}
            </div>
            <p className="insight-summary">{data.meaning}</p>
            <div className="tip-box">
              <strong>What to do</strong>
              <p className="muted">{data.action}</p>
            </div>
          </>
        ) : (
          <div className="empty-state">Loading explanation…</div>
        )}
      </div>
    </div>,
    document.body,
  );
}

export function BaselinePanel({ data }: { data: BaselineResponse | null }) {
  if (!data) {
    return (
      <div className="panel">
        <div className="empty-state">Loading baseline comparison…</div>
      </div>
    );
  }
  if (!data.available) {
    return (
      <div className="panel">
        <div className="section-head">
          <div>
            <p className="section-kicker">Credibility</p>
            <h2 className="section-title">Beat the baseline</h2>
          </div>
        </div>
        <div className="empty-state">{data.note || "Baseline unavailable."}</div>
      </div>
    );
  }

  const overall = data.overall!;
  return (
    <div className="panel insight-panel">
      <div className="section-head">
        <div>
          <p className="section-kicker">Credibility</p>
          <h2 className="section-title">Beat the baseline</h2>
        </div>
        <span className="section-icon">★</span>
      </div>
      <p className="section-sub">{data.note}</p>
      <div className="stat-row">
        <div className="stat-card">
          <p className="stat-label">Horizons beaten</p>
          <p className="stat-value">
            {overall.horizons_beaten}/{overall.horizons_total}
          </p>
          <span className="stat-hint">vs persistence</span>
        </div>
        <div className="stat-card">
          <p className="stat-label">Avg MAE gain</p>
          <p className="stat-value">{overall.avg_mae_improvement_pct}%</p>
          <span className="stat-hint">lower error</span>
        </div>
        <div className="stat-card">
          <p className="stat-label">Beat rate</p>
          <p className="stat-value">{(overall.beat_rate * 100).toFixed(0)}%</p>
          <span className="stat-hint">of horizons</span>
        </div>
      </div>
      {!!data.horizons?.length && (
        <div className="table-wrap" style={{ marginTop: "1rem" }}>
          <table className="table">
            <thead>
              <tr>
                <th>Horizon</th>
                <th>Model MAE</th>
                <th>Baseline MAE</th>
                <th>Gain</th>
                <th>Result</th>
              </tr>
            </thead>
            <tbody>
              {data.horizons.map((h) => (
                <tr key={h.horizon_hours} className={h.beats_baseline ? "winner-row" : undefined}>
                  <td>+{h.horizon_hours}h</td>
                  <td>{h.model_mae}</td>
                  <td>{h.baseline_mae}</td>
                  <td>{h.mae_improvement_pct}%</td>
                  <td>
                    <span className={`badge ${h.beats_baseline ? "badge-hit" : "badge-miss"}`}>
                      {h.beats_baseline ? "beats" : "ties/loses"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export function PipelinePanel({ data }: { data: PipelineResponse | null }) {
  if (!data) {
    return (
      <div className="panel">
        <div className="empty-state">Loading pipeline health…</div>
      </div>
    );
  }

  return (
    <div className="panel insight-panel">
      <div className="section-head">
        <div>
          <p className="section-kicker">MLOps</p>
          <h2 className="section-title">Pipeline health</h2>
        </div>
        <span className={`pipeline-overall status-${data.overall}`}>{data.overall_label}</span>
      </div>
      <p className="section-sub">Freshness of features, models, monitoring, and storage.</p>
      <div className="pipeline-list">
        {data.checks.map((c) => (
          <div className={`pipeline-row status-${c.status}`} key={c.id}>
            <span className="pipeline-dot" />
            <div className="pipeline-text">
              <strong>{c.label}</strong>
              <span>{c.detail}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
