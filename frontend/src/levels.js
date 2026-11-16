export const LEVELS = {
  Low:     { color: "#3d8c7a", letter: "L", meaning: "Normal conditions" },
  Watch:   { color: "#e3a72f", letter: "W", meaning: "2 warning signs. Stay alert" },
  High:    { color: "#c0392b", letter: "H", meaning: "All 3 warning signs. Act now" },
  Unknown: { color: "#9aa6aa", letter: "?", meaning: "No recent satellite image" },
};

export const levelOf = (l) => LEVELS[l] || LEVELS.Unknown;

export function addDays(iso, n) {
  const d = new Date(iso + "T00:00:00Z");
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}
