const BASE = import.meta.env.VITE_API_URL || "";

async function get(path) {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch { /* not JSON */ }
    throw new Error(detail);
  }
  return res.json();
}

export const api = {
  meta: () => get("/api/meta"),
  map: (date) => get(`/api/map${date ? `?date=${date}` : ""}`),
  zone: (id, date) => get(`/api/zones/${id}?date=${date}`),
  series: (id) => get(`/api/zones/${id}/series`),
  events: () => get("/api/events"),
  backtest: () => get("/api/backtest"),
  forecast: () => get("/api/forecast"),
  cards: () => get("/api/response-cards"),
};
