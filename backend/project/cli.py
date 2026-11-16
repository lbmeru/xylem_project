"""Usage: python -m project.cli <step> [<step> ...]   (steps: zones ndci weather levels events backtest forecast all)

Order matters: `levels` runs BEFORE `events`/`backtest` so the cutoffs are set first.
`forecast` needs `levels` (for the cutoffs) and internet (Open-Meteo forecast).
"""
import argparse

from . import config as C

ORDER = ["zones", "ndci", "weather", "levels", "events", "backtest", "forecast"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("steps", nargs="+", choices=ORDER + ["all"])
    args = ap.parse_args()
    steps = ORDER if "all" in args.steps else args.steps
    C.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    C.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    for s in steps:
        print(f"== {s}")
        if s == "zones":
            from . import zones; zones.run()
        elif s == "ndci":
            from . import ndci; ndci.fetch()
        elif s == "weather":
            from . import weather; weather.fetch()
        elif s == "levels":
            from . import levels; levels.run()
        elif s == "events":
            from . import events; events.run()
        elif s == "backtest":
            from . import backtest; backtest.run()
        elif s == "forecast":
            from . import forecast; forecast.run()


if __name__ == "__main__":
    main()
