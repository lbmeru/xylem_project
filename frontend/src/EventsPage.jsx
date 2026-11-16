import { useEffect, useState } from "react";
import { api } from "./api.js";
import { levelOf } from "./levels.js";

const RESULT = { hit: "Hit", miss: "Miss", no_data: "No data" };

export default function EventsPage() {
  const [bt, setBt] = useState(null);
  const [events, setEvents] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.backtest().then(setBt).catch((e) => setError(e.message));
    api.events().then(setEvents).catch(() => {});
  }, []);

  if (error) return <main className="notice"><h1>Can't load results</h1><p>{error}</p></main>;
  if (!bt) return <main className="notice"><p>Loading…</p></main>;

  const s = bt.summary;
  const undated = events.filter((e) => !e.date);
  const byId = Object.fromEntries(events.map((e) => [e.id, e]));
  const days = bt.meta.lookback_days;
  const anyApprox = bt.events.some((e) => byId[e.id]?.date_precision === "approx");

  return (
    <main className="events-page">
      <h1>How the rule did on past fish kills</h1>
      <p className="lede">
        We looked at the {days} days before each of {s.events_tested} reported fish kills.
        {" "}<strong>{s.hits}</strong> {s.hits === 1 ? "zone" : "zones"} showed Watch or High at least once,
        and <strong>{s.misses}</strong> never did{s.no_data > 0 && <>; <strong>{s.no_data}</strong> had no data</>}.
        Across the whole record, <strong>{s.false_alarm_zone_weeks}</strong> of {s.zone_weeks_high} zone-weeks
        at High had no reported fish kill.
      </p>

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
                  <td>
                    {ev?.source_url
                      ? <a href={ev.source_url} target="_blank" rel="noreferrer">{ev.source_name || "Link"}</a>
                      : <span className="muted">{ev?.source_name || ""}</span>}
                  </td>
                </tr>
              );
            })}
            {undated.map((e) => (
              <tr key={e.id} className="undated">
                <td>{e.place}</td><td colSpan="5">Reported {e.month || ""}. Needs an exact date before it can be tested.</td>
              </tr>
            ))}
            {bt.skipped?.filter((x) => x.reason !== "no exact date").map((x) => (
              <tr key={x.id} className="undated">
                <td>{byId[x.id]?.place || x.id}</td><td colSpan="5">Not tested: {x.reason}.</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {anyApprox && (
        <p className="muted table-note">
          ~ The news gave no exact day. The date is the closest day the reports give, such as the first collection or report date.
        </p>
      )}

      <section className="about" aria-labelledby="about-h">
        <h2 id="about-h">About this check</h2>
        <p>
          Bantay Lawa is a simple rule, not a trained model, checked against about {s.events_total} fish kills
          reported in the news. That is too few to say how accurate it is, and it is not a guarantee that a
          zone is safe or unsafe. Unreported fish kills would turn some false alarms into correct warnings.
        </p>
        <p className="muted">Data through {bt.meta.as_of}.</p>
      </section>
    </main>
  );
}
