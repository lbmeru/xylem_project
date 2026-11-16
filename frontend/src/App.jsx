import { useEffect, useState } from "react";
import MapPage from "./MapPage.jsx";
import EventsPage from "./EventsPage.jsx";
import AboutPage from "./AboutPage.jsx";

const ROUTES = { "#/events": "events", "#/about": "about" };
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
          <span className="brand-name">Lake Breathing</span>
          <span className="brand-sub">First Form: Enhanced Monitoring System</span>
        </a>
        <nav aria-label="Main">
          <a href="#/" aria-current={current("map")}>Map</a>
          <a href="#/events" aria-current={current("events")}>Past events</a>
          <a href="#/about" aria-current={current("about")}>About</a>
        </nav>
      </header>
      {route === "events" ? <EventsPage /> : route === "about" ? <AboutPage /> : <MapPage />}
    </div>
  );
}
