import { useEffect, useState } from "react";
import MapPage from "./MapPage.jsx";
import EventsPage from "./EventsPage.jsx";

const routeOf = () => (window.location.hash === "#/events" ? "events" : "map");

export default function App() {
  const [route, setRoute] = useState(routeOf());

  useEffect(() => {
    const onHash = () => setRoute(routeOf());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  return (
    <div className="app">
      <header className="top">
        <a className="brand" href="#/">
          <span className="brand-name">Bantay Lawa</span>
          <span className="brand-sub">Fish-kill risk, Laguna de Bay</span>
        </a>
        <nav aria-label="Main">
          <a href="#/" aria-current={route === "map" ? "page" : undefined}>Map</a>
          <a href="#/events" aria-current={route === "events" ? "page" : undefined}>Past events</a>
        </nav>
      </header>
      {route === "events" ? <EventsPage /> : <MapPage />}
    </div>
  );
}
