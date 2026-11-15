export const LEVELS = {
  Low:     { color: "#3d8c7a", letter: "L", meaning: "0 or 1 of the 3 signals is yes" },
  Watch:   { color: "#e3a72f", letter: "W", meaning: "2 of the 3 signals are yes" },
  High:    { color: "#c0392b", letter: "H", meaning: "All 3 signals are yes" },
  Unknown: { color: "#9aa6aa", letter: "?", meaning: "No clear satellite image in the last 10 days, or weather data is missing" },
};

export const levelOf = (l) => LEVELS[l] || LEVELS.Unknown;

export function addDays(iso, n) {
  const d = new Date(iso + "T00:00:00Z");
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}
