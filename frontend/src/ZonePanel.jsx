import { useEffect, useState } from "react";
import { api } from "./api.js";
import { levelOf } from "./levels.js";
import NdciChart from "./NdciChart.jsx";

function Signal({ title, value, rule, yes }) {
  const state = yes === null ? "no data" : yes ? "Yes" : "No";
  return (
    <li className="signal" data-state={state}>
      <div>
        <strong>{title}</strong>
        <span className="value">{value}</span>
        <span className="rule">{rule}</span>
      </div>
      <span className="yn">{state}</span>
    </li>
  );
}

const fmt = (v, nd, unit = "") => (v === null || v === undefined ? "no reading" : `${v.toFixed(nd)}${unit}`);

function ResponseCard({ level, cards }) {
  if (!cards) return null;
  const c = cards.levels?.[level];
  return (
    <section className="response">
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

export default function ZonePanel({ zoneId, date, cards }) {
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
        <p>Select a square on the map to see why it has its level and what to do about it.</p>
      </div>
    );
  }
  if (error) return <div className="panel"><p role="alert">{error}</p></div>;
  if (!zone || zone.zone_id !== zoneId) return <div className="panel"><p>Loading zone…</p></div>;

  const L = levelOf(zone.level);
  const th = zone.thresholds;
  const s = zone.signals;
  const yn = (v) => (v === null || v === undefined ? null : v === 1);

  return (
    <div className="panel">
      <div className="panel-head">
        <div>
          <h2>{zone.label}</h2>
          <p className="muted">{zone.area_km2} km² · {zone.date}</p>
        </div>
        <span className="badge" style={{ background: L.color }}>{L.letter} {zone.level}</span>
      </div>
      <p className="muted">{L.meaning}.</p>

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

      <ResponseCard level={zone.level} cards={cards} />

      <section>
        <h3>Algae signal over time</h3>
        {series ? <NdciChart series={series} date={date} /> : <p className="muted">Loading chart…</p>}
      </section>
    </div>
  );
}
