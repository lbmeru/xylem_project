import { useEffect, useState } from "react";
import { api } from "./api.js";
import { levelOf } from "./levels.js";
import NdciChart from "./NdciChart.jsx";

const asDate = (iso) => new Date(iso + "T00:00:00Z");
const longDate = (iso) => asDate(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
const shortDate = (iso) => asDate(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "UTC" });
const dayLabel = (iso) => asDate(iso).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short", timeZone: "UTC" });

function Signal({ title, yes, detail }) {
  const state = yes === null ? "No data" : yes ? "Yes" : "No";
  return (
    <li className="signal" data-state={state}>
      <span className="name">{title}</span>
      <span className="yn">{state}</span>
      <span className="detail">{detail}</span>
    </li>
  );
}

/* "26.2 °C (flagged at 30.4 or more)" */
function detail(value, nd, unit, cutoff, side) {
  if (value === null || value === undefined) return "No reading";
  const v = `${value.toFixed(nd)}${unit}`;
  return cutoff == null ? v : `${v} (flagged at ${cutoff.toFixed(nd)} or ${side})`;
}

function ResponseCard({ level, cards }) {
  const actions = cards?.levels?.[level]?.actions;
  if (!actions?.length) return null;
  return (
    <section className="block response">
      <h3>What to do</h3>
      <ul>
        {actions.map((a) => (
          <li key={a.text}>
            {a.text}
            {a.source && !/app guidance/i.test(a.source) && <span className="src"> ({a.source})</span>}
          </li>
        ))}
      </ul>
      {level === "High" && cards.limit && <p className="limit">{cards.limit}</p>}
    </section>
  );
}

function Forecast({ forecast, zoneId }) {
  if (!forecast) return null;
  const z = forecast.zones?.[zoneId];
  const beat = forecast.meta?.validation?.beats_persistence === true && forecast.meta?.model !== "persistence";
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
                  </tr>
                );
              })}
            </tbody>
          </table>
          <p className="muted">
            {beat ? "Beat a no-change guess in testing." : "No better than a no-change guess in testing."}
          </p>
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
        <p>Click a zone on the map.</p>
      </div>
    );
  }
  if (error) return <div className="panel"><p className="block" role="alert">{error}</p></div>;
  if (!zone || zone.zone_id !== zoneId) return <div className="panel"><p className="block">Loading zone…</p></div>;

  const L = levelOf(zone.level);
  const th = zone.thresholds;
  const s = zone.signals;
  const yn = (v) => (v === null || v === undefined ? null : v === 1);
  const algae = detail(zone.ndci, 2, "", th?.ndci_p80, "more");

  return (
    <div className="panel">
      <header className="zone-head">
        <h2>{zone.label}</h2>
        <p className="muted">{longDate(zone.date)}</p>
      </header>
      <div className={`status s-${zone.level.toLowerCase()}`}>
        <strong>{zone.level}</strong>
        <span>{L.meaning}</span>
      </div>

      <section className="block">
        <ul className="signals">
          <Signal title="Algae" yes={yn(s.algae_high)}
                  detail={zone.ndci_date ? `${algae}. Image: ${shortDate(zone.ndci_date)}` : algae} />
          <Signal title="Warm" yes={yn(s.warm)} detail={detail(zone.temp_3d, 1, " °C", th?.temp3_p80, "more")} />
          <Signal title="Calm" yes={yn(s.calm)} detail={detail(zone.wind_3d, 1, " km/h", th?.wind3_p20, "less")} />
        </ul>
      </section>

      <ResponseCard level={zone.level} cards={cards} />
      {showForecast && <Forecast forecast={forecast} zoneId={zoneId} />}

      <section className="block">
        <h3>Algae reading over time</h3>
        {series ? <NdciChart series={series} date={date} /> : <p className="muted">Loading chart…</p>}
      </section>
    </div>
  );
}
