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

  return (
    <main className="events-page">
      <h1>How the rule did on past fish kills</h1>
      <p className="lede">
        For each reported fish kill, we check whether its zone showed Watch or High on at least one
        of the {bt.meta.lookback_days} days before.
      </p>

      <ul className="counts">
        <li><strong>{s.hits}</strong> {s.hits === 1 ? "hit" : "hits"}</li>
        <li><strong>{s.misses}</strong> {s.misses === 1 ? "miss" : "misses"}</li>
        {s.no_data > 0 && <li><strong>{s.no_data}</strong> with no data</li>}
        <li><strong>{s.false_alarm_zone_weeks}</strong> false-alarm zone-weeks
          <span className="muted"> (High with no reported kill, out of {s.zone_weeks_high} High zone-weeks)</span></li>
      </ul>

      <div className="table-scroll">
        <table>
          <thead>
            <tr><th>Place</th><th>Date</th><th>Zone</th><th>Level, 7 days before</th><th>Result</th></tr>
          </thead>
          <tbody>
            {bt.events.map((e) => (
              <tr key={e.id}>
                <td>{e.place}</td><td>{e.date}</td><td>{e.zone_id}</td>
                <td>
                  <span className="chips">
                    {e.levels_before.map((d) => {
                      const L = levelOf(d.level);
                      return <span key={d.date} className="chip" style={{ background: L.color }}
                                   title={`${d.date}: ${d.level}`}>{L.letter}</span>;
                    })}
                  </span>
                </td>
                <td><span className={`result ${e.result}`}>{RESULT[e.result]}</span></td>
              </tr>
            ))}
            {undated.map((e) => (
              <tr key={e.id} className="undated">
                <td>{e.place}</td><td colSpan="4">Reported {e.month || ""}. Needs an exact date before it can be tested.</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <section className="about" aria-labelledby="about-h">
        <h2 id="about-h">About this check</h2>
        <p>
          project is a simple rule, not a trained model, checked against about {s.events_total} fish kills
          reported in the news. That is too few to say how accurate it is, and it is not a guarantee that a
          zone is safe or unsafe. Unreported fish kills would turn some false alarms into correct warnings.
        </p>
        <p className="muted">Data through {bt.meta.as_of}.</p>
      </section>
    </main>
  );
}
