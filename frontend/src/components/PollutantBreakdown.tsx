import type { WeatherResponse } from "../api";

type Pollutant = NonNullable<WeatherResponse["pollutants"]>[number];

export function PollutantBreakdown({
  pollutants,
  driverDetail,
}: {
  pollutants?: Pollutant[] | null;
  driverDetail?: string | null;
}) {
  if (!pollutants?.length) {
    return (
      <div className="panel pollutant-panel">
        <div className="section-head">
          <div>
            <p className="section-kicker">Air chemistry</p>
            <h2 className="section-title">Pollutant breakdown</h2>
          </div>
        </div>
        <div className="empty-state">Pollutant details load with city weather.</div>
      </div>
    );
  }

  return (
    <div className="panel pollutant-panel">
      <div className="section-head">
        <div>
          <p className="section-kicker">Air chemistry</p>
          <h2 className="section-title">Pollutant breakdown</h2>
        </div>
        <span className="section-icon">◎</span>
      </div>
      <p className="section-sub">
        Concentrations with relative intensity vs a sensitive-group reference — similar to IQAir/WAQI style
        bars (not a formal AQI share %).
      </p>
      <div className="pollutant-list">
        {pollutants.map((p) => (
          <div className={`pollutant-row ${p.is_dominant ? "is-dominant" : ""}`} key={p.key}>
            <div className="pollutant-row-head">
              <div className="pollutant-name">
                <span className="pollutant-swatch" style={{ background: p.color }} />
                <strong>{p.label}</strong>
                {p.is_dominant ? <span className="pollutant-badge">Dominant</span> : null}
              </div>
              <div className="pollutant-value">
                <strong>{p.value}</strong>
                <small>{p.unit}</small>
              </div>
            </div>
            <div className="pollutant-bar-track" aria-hidden>
              <div
                className="pollutant-bar-fill"
                style={{ width: `${p.intensity_pct}%`, background: p.color }}
              />
            </div>
            <div className="pollutant-row-foot">
              <span>{p.level}</span>
              <span>{Math.round(p.intensity_pct)}% of reference</span>
            </div>
          </div>
        ))}
      </div>
      {driverDetail ? <p className="pollutant-note">{driverDetail}</p> : null}
    </div>
  );
}
