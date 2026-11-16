# HOW TO RUN

# Lake Breathing, First Form: Enhanced Monitoring System

A web map that gives each zone of Laguna de Bay a daily fish-kill risk level (Low, Watch, High, Unknown) from free satellite and weather data.

- **Backend:** Python (data pipeline + FastAPI)
- **Frontend:** React (Vite)
- **Data:** Sentinel-2 satellite images through Google Earth Engine, and weather from Open-Meteo

## How it works

Each zone gets three yes/no checks:

1. **Algae:** the satellite algae reading (NDCI) is in the top 20% of that zone's own history.
2. **Warm:** the 3-day average air temperature is in the top 20% of its history.
3. **Calm:** the 3-day average wind speed is in the bottom 20%.

0 or 1 yes = Low, 2 = Watch, 3 = High. A zone with no clear satellite image in the last 10 days shows Unknown.

This is a simple rule, not a trained model. NDCI is a relative algae signal, not a direct algae count.

## Requirements

- Python 3.10 or newer
- Node.js 18 or newer

The generated data is already in `backend/output/`, so a fresh clone runs the website without the data pipeline. You only need a Google account and Earth Engine to refresh the data (see "Refresh the data").

## Project structure

```
Xylem_project/
├── backend/
│   ├── project/        Python code (pipeline + API)
│   ├── data/           lake outline, fish-kill events, response cards
│   ├── output/         generated JSON the website reads (committed)
│   ├── cache/          downloaded raw data (not committed, only for the pipeline)
│   └── requirements.txt
└── frontend/           React website
```

## Run the website

Use `python` instead of `python3` on Windows.

**1. Install the backend packages** (once, from the repo folder):

```bash
pip install -r backend/requirements.txt
```

**2. Terminal 1: backend API** (in `backend`):

```bash
cd backend
python3 -m uvicorn project.api:app --reload
```

Wait for `Application startup complete`. Check http://localhost:8000/api/health. It should show `{"ok":true}`.

**3. Terminal 2: website** (in `frontend`):

```bash
cd frontend
npm install
npm run dev
```

You only need `npm install` the first time. Open **http://localhost:5173** in your browser. Click a zone on the map to see its level, the three signals, what to do, the 5-day forecast and the algae chart. Use the date box to look at other days.

Stop either terminal with **Ctrl+C**.

## Refresh the data

Only needed to pull newer satellite and weather data. The website works without this.

### One-time Earth Engine setup

1. Go to https://console.cloud.google.com and sign in with a Google account.
2. Click **Select a project**, then **New project**. Name it and click **Create**.
3. Copy the **Project ID** shown under the name.
4. Open https://code.earthengine.google.com/register.
5. Choose **Unpaid usage**, then **Academic & Research** or **Non-profit**.
6. Select your project and finish the form. Choose the **Community** tier, which needs no payment card.

### Run the pipeline

In the `backend` folder, set your project ID:

```bash
export EE_PROJECT=your-project-id
```

On Windows PowerShell use `$env:EE_PROJECT="your-project-id"` instead. Run it again in every new terminal.

To pull the newest data (the usual refresh):

```bash
python3 -m project.cli weather ndci levels forecast
```

To rebuild everything from scratch:

```bash
python3 -m project.cli zones ndci weather levels events backtest forecast
```

Keep the order. `levels` fixes the cutoffs before `events` and `backtest` look at any fish kill.

The 2019 fish kills need data back to 2019, so do not set a start date for the real run. To try the pipeline quickly, set one (this makes the 2019 and 2020 events show "no data"): `BL_START_DATE=2025-01-01` (PowerShell: `$env:BL_START_DATE="2025-01-01"`).

On the first run it prints a Google sign-in link:

1. Open the link in your browser.
2. Choose your Google account and click **Generate token**, then **Allow**.
3. Copy the code shown and paste it back into the terminal. Press Enter.

You only sign in once on a computer. The satellite step can take a long time. It saves its work as it goes, so running the same command again continues from where it left off.

The results are written to `backend/output/`. The API picks up the new files on its own, so you don't need to restart it. Refresh the browser. Commit `backend/output/` so others get the new data.

## How the 5-day forecast works

`forecast` predicts each zone's algae reading (NDCI) for the next 5 days, then applies the same Low, Watch, High rule to the predicted reading and Open-Meteo's weather forecast.

- It trains on pairs of clear readings of the same zone up to 15 days apart. Inputs are the earlier reading, the recent trend, the zone's average, the season, and the weather between the two dates. The target is the change in NDCI.
- It tries "no change", ridge regression and gradient boosting. The last 20% of dates are held out as a test set and never used for training.
- If no model beats "no change" on that test set, the forecast keeps the latest NDCI and only the weather signals move. The app says which case applies and shows the test error.
- It never uses fish-kill events, so the backtest stays an independent check.
- Satellite images are blocked by cloud, so a zone with no clear image in the last 10 days has no forecast.

Check it works with `python3 -m pytest tests` in `backend`.

## Notes and limits

- The committed data is a snapshot. The map shows risk as of the last time the pipeline ran, until someone refreshes it.
- Cloudy days are lost. A zone with no clear image in the last 10 days shows grey (Unknown).
- The lake zones are squares of about 5 km cut from Earth Engine's water map.
- Air temperature stands in for water temperature, which this project does not measure.
- This is a prototype and is not a guarantee that a zone is safe or unsafe.

## Troubleshooting

| What you see | Fix |
|---|---|
| Website says "Can't load risk data" | The API is not running. Start Terminal 1 and check `backend/output/` has `daily_risk.json`. |
| `ECONNREFUSED` in the website terminal | Same as above: start the API first. |
| `No module named ...` | Install the packages: `pip install -r backend/requirements.txt` |
| `No module named project.cli` | You are not in the `backend` folder, or `backend/project/` is missing files. |
| Message asks for `EE_PROJECT` | Run `export EE_PROJECT=your-project-id` in that terminal. |
| Sign-in code rejected | Run the pipeline command again to get a new link and code. |
| Earth Engine quota error | The Community tier has a usage limit. Re-run with a later `BL_START_DATE`, or wait and run again. |
| Command not found: `python` | Use `python3`. |