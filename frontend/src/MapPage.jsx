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

export default function MapPage() {
  const [meta, setMeta] = useState(null);
  const [cards, setCards] = useState(null);
  const [date, setDate] = useState(null);
  const [data, setData] = useState(null);
  const [zoneId, setZoneId] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.meta().then((m) => { setMeta(m); setDate(m.last_date); }).catch((e) => setError(e.message));
    api.cards().then(setCards).catch(() => setCards(null));
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
  const style = (f) => {
    const sel = f.properties.zone_id === zoneId;
    return { fillColor: levelOf(f.properties.level).color, fillOpacity: 0.72,
             color: sel ? "#14262b" : "#ffffff", weight: sel ? 3 : 1 };
  };

  return (
    <main className="map-page">
      <section className="map-col">
        <div className="map-bar">
          <DateControls meta={meta} date={date} setDate={setDate} />
          <p className="asof">
            {isLatest
              ? <>Risk as of <strong>{meta.as_of}</strong>. Weather data arrives about 5 days late, so this is not live.</>
              : <>Showing <strong>{date}</strong>. Latest data is from {meta.last_date}.</>}
          </p>
        </div>
        <div className="map-wrap">
          <MapContainer center={[14.37, 121.2]} zoom={10} className="map">
            <TileLayer attribution='&copy; OpenStreetMap contributors &copy; CARTO'
                       url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png" />
            <GeoJSON key={`${date}-${zoneId}`} data={data} style={style}
                     onEachFeature={(f, layer) => {
                       layer.bindTooltip(`${f.properties.label}: ${f.properties.level}`, { sticky: true });
                       layer.on("click", () => setZoneId(f.properties.zone_id));
                     }} />
            <FitBounds data={data} />
          </MapContainer>
          <ul className="legend" aria-label="Legend">
            {Object.entries(LEVELS).map(([name, l]) => (
              <li key={name}><span className="swatch" style={{ background: l.color }}>{l.letter}</span>{name}</li>
            ))}
          </ul>
        </div>
      </section>
      <aside className="panel-col">
        <ZonePanel zoneId={zoneId} date={date} cards={cards} />
      </aside>
    </main>
  );
}
