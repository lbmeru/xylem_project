import { useEffect, useState } from "react";
import { api } from "./api.js";
import { levelOf } from "./levels.js";

const RESULT = { hit: "Hit", miss: "Miss", no_data: "No data" };
const monthLabel = (ym) => (ym
  ? new Date(ym + "-01T00:00:00Z").toLocaleDateString("en-GB", { month: "long", year: "numeric", timeZone: "UTC" })
  : "");

export default function EventsPage() {
  const [bt, setBt] = useState(null);
  const [events, setEvents] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.backtest().then(setBt).catch((e) => setError(e.message));
    api.events().then(setEvents).catch(() => {});
  }, []);

  if (error) return <main className="notice"><h1>Can't load results</h1><p>Please try again later.</p></main>;
  if (!bt) return <main className="notice"><p>Loading…</p></main>;

  const s = bt.summary;
  const undated = events.filter((e) => !e.date);
  const byId = Object.fromEntries(events.map((e) => [e.id, e]));
  const days = bt.meta.lookback_days;
  const anyApprox = bt.events.some((e) => byId[e.id]?.date_precision === "approx");

  return (
    <main className="events-page">
      <h1>Did the map warn before past fish kills?</h1>
      <p className="lede">Hit means the zone showed Watch or High at least once in the {days} days before.</p>
      <ul className="tally counts" aria-label="Results">
        <li><strong>{s.hits}</strong>{s.hits === 1 ? "hit" : "hits"}</li>
        <li><strong>{s.misses}</strong>{s.misses === 1 ? "miss" : "misses"}</li>
        <li><strong>{s.no_data}</strong>no data</li>
      </ul>
      <p>{s.false_alarm_zone_weeks} of {s.zone_weeks_high} High zone-weeks had no reported fish kill.</p>

      <div className="table-scroll">
        <table>
          <thead>
            <tr><th>Place</th><th>Date</th><th>Zone</th><th>Level, {days} days before</th><th>Result</th><th>Source</th></tr>
          </thead>
          <tbody>
            {bt.events.map((e) => {
              const ev = byId[e.id];
              return (
                <tr key={e.id}>
                  <td>{e.place}</td>
                  <td>{ev?.date_precision === "approx" ? "~" : ""}{e.date}</td>
                  <td>{e.zone_id}</td>
                  <td>
                    <span className="chips">
                      {e.levels_before.map((d) => {
                        const L = levelOf(d.level);
                        return <span key={d.date} className={`chip ${d.level.toLowerCase()}`} style={{ background: L.color }}
                                     title={`${d.date}: ${d.level}`}>{L.letter}</span>;
                      })}
                    </span>
                  </td>
                  <td><span className={`result ${e.result}`}>{RESULT[e.result]}</span></td>
                  <td><Source ev={ev} /></td>
                </tr>
              );
            })}
            {undated.map((e) => (
              <tr key={e.id} className="undated">
                <td>{e.place}</td>
                <td colSpan="4">{monthLabel(e.month)}. No exact date, so not tested.</td>
                <td><Source ev={e} /></td>
              </tr>
            ))}
            {bt.skipped?.filter((x) => x.reason !== "no exact date").map((x) => (
              <tr key={x.id} className="undated">
                <td>{byId[x.id]?.place || x.id}</td>
                <td colSpan="4">Not tested.</td>
                <td><Source ev={byId[x.id]} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {anyApprox && <p className="muted table-note">~ Approximate date.</p>}

      <p className="about-line">
        A simple rule checked on {s.events_tested} news-reported fish kills. Too few to measure accuracy, and not
        a guarantee. <a href="#/about">About this project</a>
      </p>
    </main>
  );
}

function Source({ ev }) {
  if (!ev) return null;
  return ev.source_url
    ? <a href={ev.source_url} target="_blank" rel="noreferrer">{ev.source_name || "Link"}</a>
    : <span className="muted">{ev.source_name || ""}</span>;
}
