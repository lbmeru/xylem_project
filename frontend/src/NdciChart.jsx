const W = 560, H = 190, M = { l: 40, r: 12, t: 14, b: 26 };
const t = (iso) => Date.parse(iso + "T00:00:00Z");

export default function NdciChart({ series, date }) {
  const obs = series.ndci_observations;
  if (!obs.length) return <p className="muted">No clear satellite readings for this zone yet.</p>;

  const th = series.ndci_threshold;
  const xs = obs.map((o) => t(o.date));
  const x0 = Math.min(...xs), x1 = Math.max(...xs);
  const ys = obs.map((o) => o.ndci).concat(th ?? []);
  const lo = Math.min(...ys), hi = Math.max(...ys);
  const pad = (hi - lo) * 0.08 || 0.05;
  const X = (ms) => M.l + ((ms - x0) / (x1 - x0 || 1)) * (W - M.l - M.r);
  const Y = (v) => H - M.b - ((v - (lo - pad)) / (hi - lo + 2 * pad)) * (H - M.t - M.b);

  const years = [];
  for (let y = new Date(x0).getUTCFullYear() + 1; y <= new Date(x1).getUTCFullYear(); y++) years.push(y);
  const path = obs.map((o, i) => `${i ? "L" : "M"}${X(t(o.date)).toFixed(1)},${Y(o.ndci).toFixed(1)}`).join(" ");

  return (
    <figure className="chart">
      <svg viewBox={`0 0 ${W} ${H}`} role="img"
           aria-label="NDCI at each clear satellite image, with the cutoff and past fish kills marked">
        {[lo, (lo + hi) / 2, hi].map((v) => (
          <g key={v}>
            <line x1={M.l} x2={W - M.r} y1={Y(v)} y2={Y(v)} className="grid" />
            <text x={M.l - 6} y={Y(v) + 4} textAnchor="end" className="tick">{v.toFixed(2)}</text>
          </g>
        ))}
        {years.map((y) => (
          <text key={y} x={X(Date.UTC(y, 0, 1))} y={H - 8} textAnchor="middle" className="tick">{y}</text>
        ))}
        {th != null && <line x1={M.l} x2={W - M.r} y1={Y(th)} y2={Y(th)} className="cutoff" />}
        <path d={path} className="line" />
        {obs.map((o) => <circle key={o.date} cx={X(t(o.date))} cy={Y(o.ndci)} r="2" className="dot"><title>{o.date}: {o.ndci}</title></circle>)}
        {series.events.map((e) => (e.date && t(e.date) >= x0 && t(e.date) <= x1) && (
          <g key={e.id}>
            <line x1={X(t(e.date))} x2={X(t(e.date))} y1={M.t} y2={H - M.b} className="event" />
            <title>Fish kill, {e.place}, {e.date}</title>
          </g>
        ))}
        {t(date) >= x0 && t(date) <= x1 && <line x1={X(t(date))} x2={X(t(date))} y1={M.t} y2={H - M.b} className="today" />}
      </svg>
      <figcaption>
        <span className="key cutoff-key">Dashed: algae cutoff</span>
        <span className="key event-key">Red: reported fish kill</span>
        <span className="key today-key">Dark: selected date</span>
      </figcaption>
    </figure>
  );
}
