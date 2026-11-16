import { useEffect, useState } from "react";
import { MapContainer, TileLayer, GeoJSON, useMap } from "react-leaflet";
import L from "leaflet";
import { api } from "./api.js";
import { LEVELS, levelOf, addDays } from "./levels.js";
import ZonePanel from "./ZonePanel.jsx";

function FitBounds({ data }) {
  const map = useMap();
  useEffect(() => {
    if (data?.features?.length) map.fitBounds(L.geoJSON(data).getBounds(), { padding: [20, 20] });
    // fit once, when zones first load
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data?.features?.length]);
  return null;
}

function DateControls({ meta, date, setDate }) {
  const { first_date: min, last_date: max } = meta;
  const step = (n) => {
    const next = addDays(date, n);
    if (next >= min && next <= max) setDate(next);
  };
  return (
    <div className="date-controls">
      <button onClick={() => step(-1)} disabled={date <= min} aria-label="Previous day">‹</button>
      <input type="date" value={date} min={min} max={max}
             onChange={(e) => e.target.value && setDate(e.target.value)} aria-label="Date" />
      <button onClick={() => step(1)} disabled={date >= max} aria-label="Next day">›</button>
      <button className="text" onClick={() => setDate(max)} disabled={date === max}>Latest</button>
    </div>
  );
}

/* Fill patterns so level is readable without colour: hatch for Watch, cross-hatch for High, dots for Unknown. */
function Patterns() {
  return (
    <svg width="0" height="0" style={{ position: "absolute" }} aria-hidden="true" focusable="false">
      <defs>
        <pattern id="p-watch" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <rect width="7" height="7" fill="#e2a400" /><rect width="2" height="7" fill="#7a5700" />
        </pattern>
        <pattern id="p-high" width="6" height="6" patternUnits="userSpaceOnUse">
          <rect width="6" height="6" fill="#c62f1c" />
          <path d="M0 0L6 6M6 0L0 6" stroke="#5c1208" strokeWidth="1.2" />
        </pattern>
        <pattern id="p-unknown" width="6" height="6" patternUnits="userSpaceOnUse">
          <rect width="6" height="6" fill="#66757b" /><circle cx="3" cy="3" r="1" fill="#e8eeef" />
        </pattern>
      </defs>
    </svg>
  );
}

export default function MapPage() {
  const [meta, setMeta] = useState(null);
  const [cards, setCards] = useState(null);
  const [forecast, setForecast] = useState(undefined);
  const [date, setDate] = useState(null);
  const [data, setData] = useState(null);
  const [zoneId, setZoneId] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.meta().then((m) => { setMeta(m); setDate(m.last_date); }).catch((e) => setError(e.message));
    api.cards().then(setCards).catch(() => setCards(null));
    api.forecast().then(setForecast).catch(() => setForecast(null));
  }, []);

  useEffect(() => {
    if (!date) return;
    api.map(date).then((d) => { setData(d); setError(null); }).catch((e) => setError(e.message));
  }, [date]);

  if (error && !meta) {
    return <main className="notice"><h1>Can't load risk data</h1><p>{error}</p>
      <p>Start the API with <code>uvicorn project.api:app</code> and run the data pipeline first.</p></main>;
  }
  if (!meta || !data) return <main className="notice"><p>Loading map…</p></main>;

  const isLatest = date === meta.last_date;
  const tally = { Low: 0, Watch: 0, High: 0, Unknown: 0 };
  data.features.forEach((f) => { tally[levelOf(f.properties.level).letter === "?" ? "Unknown" : f.properties.level] += 1; });

  const style = (f) => {
    const sel = f.properties.zone_id === zoneId;
    const lvl = levelOf(f.properties.level);
    return { className: `z-${(LEVELS[f.properties.level] ? f.properties.level : "Unknown").toLowerCase()}`,
             fillColor: lvl.color, fillOpacity: 0.92,
             color: sel ? "#0f2430" : "#ffffff", weight: sel ? 3 : 1 };
  };

  return (
    <main className="map-page">
      <Patterns />
      <section className="map-col">
        <div className="map-bar">
          <DateControls meta={meta} date={date} setDate={setDate} />
          <ul className="tally" aria-label="Zones by level">
            {["High", "Watch", "Low", "Unknown"].filter((k) => k !== "Unknown" || tally.Unknown > 0).map((k) => (
              <li key={k}><strong>{tally[k]}</strong>{k}</li>
            ))}
          </ul>
          <p className="asof">
            {isLatest
              ? <>Risk as of <strong>{meta.as_of}</strong>. Weather data arrives about 5 days late, so this is not live.</>
              : <>Showing <strong>{date}</strong>. Latest data is from {meta.last_date}.</>}
          </p>
        </div>
        <div className="map-wrap">
          <MapContainer center={[14.37, 121.2]} zoom={10} className="map">
            <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                       url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" />
            <GeoJSON key={`${date}-${zoneId}`} data={data} style={style}
                     onEachFeature={(f, layer) => {
                       const p = f.properties;
                       layer.bindTooltip(p.ndci == null ? "no image" : p.ndci.toFixed(2),
                                         { permanent: true, direction: "center", className: "sounding", opacity: 1 });
                       layer.on("click", () => setZoneId(p.zone_id));
                     }} />
            <FitBounds data={data} />
          </MapContainer>
          <ul className="legend" aria-label="Legend">
            {Object.keys(LEVELS).map((name) => (
              <li key={name}><span className={`key key-${name.toLowerCase()}`} />{name}</li>
            ))}
            <li className="legend-note">Number on each zone: algae reading (NDCI)</li>
          </ul>
        </div>
      </section>
      <aside className="panel-col">
        <ZonePanel zoneId={zoneId} date={date} cards={cards} forecast={forecast} showForecast={isLatest} />
      </aside>
    </main>
  );
}
