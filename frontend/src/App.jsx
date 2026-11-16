import { useEffect, useState } from "react";
import MapPage from "./MapPage.jsx";
import EventsPage from "./EventsPage.jsx";

const ROUTES = { "#/events": "events" };
const routeOf = () => ROUTES[window.location.hash] || "map";

export default function App() {
  const [route, setRoute] = useState(routeOf());

  useEffect(() => {
    const onHash = () => { setRoute(routeOf()); window.scrollTo(0, 0); };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const current = (r) => (route === r ? "page" : undefined);

  return (
    <div className="app">
      <header className="top">
        <a className="brand" href="#/">
          <span className="brand-name">Lake Breathing, First Form</span>
          <span className="brand-sub">Enhanced Monitoring System</span>
        </a>
        <nav aria-label="Main">
          <a href="#/" aria-current={current("map")}>Map</a>
          <a href="#/events" aria-current={current("events")}>Past events</a>
        </nav>
      </header>
      {route === "events" ? <EventsPage /> : <MapPage />}
    </div>
  );
}
