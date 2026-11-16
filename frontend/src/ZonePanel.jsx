import { useEffect, useState } from "react";
import { api } from "./api.js";
import { levelOf } from "./levels.js";
import NdciChart from "./NdciChart.jsx";

function Signal({ title, value, rule, yes }) {
  const state = yes === null ? "no data" : yes ? "Yes" : "No";
  return (
    <li className="signal" data-state={state}>
      <span className="name">{title}</span>
      <span className="yn">{state}</span>
      <span className="value">{value}</span>
      <span className="rule">{rule}</span>
    </li>
  );
}

const fmt = (v, nd, unit = "") => (v === null || v === undefined ? "no reading" : `${v.toFixed(nd)}${unit}`);
const f2 = (v) => { const s = v.toFixed(2); return s === "-0.00" ? "0.00" : s; };
const MODEL_NAME = { ridge: "ridge regression", gbm: "gradient boosting" };

function ResponseCard({ level, cards }) {
  if (!cards) return null;
  const c = cards.levels?.[level];
  return (
    <section className="block response">
      <h3>What to do at {level}</h3>
      <ul>
        {c?.actions.map((a) => (
          <li key={a.text}>{a.text}{a.source && <span className="src"> ({a.source})</span>}</li>
        ))}
      </ul>
      {level === "High" && <p className="limit">{cards.limit}</p>}
    </section>
  );
}

function validationNote(meta) {
  const v = meta?.validation;
  if (!v) return null;
  if (v.test_mae == null) {
    return `${v.reason || "No model was trained."} The forecast keeps the latest algae reading and only the weather signals move.`;
  }
  if (meta.model === "persistence") {
    return `Tested on ${v.n_test} past readings from ${v.test_from} on. No model beat "no change" (average NDCI error ${v.test_mae_persistence}), so this forecast keeps the latest algae reading and only the weather signals move.`;
  }
  return `Model: ${MODEL_NAME[meta.model] || meta.model}. Tested on ${v.n_test} past readings from ${v.test_from} on: average NDCI error ${v.test_mae}, against ${v.test_mae_persistence} if we assume no change.`;
}

const dayLabel = (iso) => new Date(iso + "T00:00:00Z")
  .toLocaleDateString("en-PH", { weekday: "short", day: "numeric", month: "short", timeZone: "UTC" });

function Forecast({ forecast, zoneId }) {
  if (forecast === undefined) return null;
  if (forecast === null) {
    return (
      <section className="block">
        <h3>Next 5 days</h3>
        <p className="muted">No forecast yet. Run <code>python -m project.cli forecast</code> in the backend folder.</p>
      </section>
    );
  }
  const z = forecast.zones?.[zoneId];
  return (
    <section className="block">
      <h3>Next 5 days</h3>
      {!z || !z.days.length ? (
        <p className="muted">{z?.reason || "No forecast for this zone."}</p>
      ) : (
        <>
          <table className="fc">
            <tbody>
              {z.days.map((d) => {
                const L = levelOf(d.level);
                return (
                  <tr key={d.date}>
                    <th scope="row">{dayLabel(d.date)}</th>
                    <td>
                      <span className="lvl">
                        <span className={`sq ${d.level.toLowerCase()}`} style={{ background: L.color }}>{L.letter}</span>
                        {d.level}
                      </span>
                    </td>
                    <td>
                      {d.ndci == null ? <span className="muted">no weather</span> : <>
                        {f2(d.ndci)} <span className="muted">({f2(d.ndci_low)} to {f2(d.ndci_high)})</span>
                      </>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <p className="muted">
            Starts from the satellite image of {z.base_date}. Weather is Open-Meteo's forecast. Numbers are
            the predicted algae reading and its likely range.
          </p>
          <p className="muted">{validationNote(forecast.meta)}</p>
        </>
      )}
    </section>
  );
}

export default function ZonePanel({ zoneId, date, cards, forecast, showForecast }) {
  const [zone, setZone] = useState(null);
  const [series, setSeries] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!zoneId) return;
    setSeries(null);
    api.series(zoneId).then(setSeries).catch((e) => setError(e.message));
  }, [zoneId]);

  useEffect(() => {
    if (!zoneId || !date) return;
    api.zone(zoneId, date).then((z) => { setZone(z); setError(null); }).catch((e) => setError(e.message));
  }, [zoneId, date]);

  if (!zoneId) {
    return (
      <div className="panel empty">
        <h2>Pick a zone</h2>
        <p>Select a square on the map to see why it has its level, what to do, and the forecast.</p>
      </div>
    );
  }
  if (error) return <div className="panel"><p className="block" role="alert">{error}</p></div>;
  if (!zone || zone.zone_id !== zoneId) return <div className="panel"><p className="block">Loading zone…</p></div>;

  const L = levelOf(zone.level);
  const th = zone.thresholds;
  const s = zone.signals;
  const yn = (v) => (v === null || v === undefined ? null : v === 1);

  return (
    <div className="panel">
      <header className="zone-head">
        <h2>{zone.label}</h2>
        <p className="muted">{zone.area_km2} km², {zone.date}</p>
      </header>
      <div className={`status s-${zone.level.toLowerCase()}`}>
        <strong>{zone.level}</strong>
        <span>{L.meaning}</span>
      </div>

      <section className="block">
        <ul className="signals">
          <Signal title="Algae" value={`NDCI ${fmt(zone.ndci, 2)}`} yes={yn(s.algae_high)}
                  rule={th ? `Yes at ${th.ndci_p80.toFixed(2)} or higher (top 20% for this zone)` : "Not enough images for a cutoff"} />
          <Signal title="Warm" value={`${fmt(zone.temp_3d, 1, " °C")} (3-day average)`} yes={yn(s.warm)}
                  rule={th ? `Yes at ${th.temp3_p80.toFixed(1)} °C or higher (top 20%)` : "No cutoff"} />
          <Signal title="Calm" value={`${fmt(zone.wind_3d, 1, " km/h")} (3-day average)`} yes={yn(s.calm)}
                  rule={th ? `Yes at ${th.wind3_p20.toFixed(1)} km/h or lower (bottom 20%)` : "No cutoff"} />
        </ul>
        {zone.ndci_date && (
          <p className="muted">Algae reading comes from the satellite image of {zone.ndci_date}
            {zone.ndci_age_days > 0 ? `, ${zone.ndci_age_days} day${zone.ndci_age_days > 1 ? "s" : ""} before this date` : ""}.</p>
        )}
      </section>

      <ResponseCard level={zone.level} cards={cards} />
      {showForecast
        ? <Forecast forecast={forecast} zoneId={zoneId} />
        : <section className="block"><h3>Next 5 days</h3>
            <p className="muted">The forecast starts from the latest data. Press Latest to see it.</p></section>}

      <section className="block">
        <h3>Algae reading over time</h3>
        {series ? <NdciChart series={series} date={date} /> : <p className="muted">Loading chart…</p>}
      </section>
    </div>
  );
}
