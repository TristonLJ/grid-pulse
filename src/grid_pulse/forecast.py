"""Forecast South Africa's coal share of generation.

Two questions, two methods:

1. The next 12 months: a monthly forecast. Candidate models are compared by rolling-origin
   backtesting (stand at each past month, forecast ahead, score against what happened).
   The most accurate model is used, and its prediction bands come from its own backtest
   errors, so they show how wrong it has actually been rather than a textbook formula.
2. When could coal fall below 70%? Too far out for a monthly model, so we extend the
   annual trend fitted over several windows and report the spread as a scenario range.

Pure numpy: pandas is blocked on the dev machine and isn't needed.

Usage:  python -m grid_pulse.forecast
"""

from datetime import date
from functools import partial

import duckdb
import numpy as np

from grid_pulse.ingest import DB_PATH

HORIZON = 12      # months ahead
MIN_TRAIN = 48    # months of history before the first backtest origin
TARGET = 70.0     # coal share threshold for the scenario question
SCENARIO_WINDOWS = {"Since 2021": 2021, "Since 2018": 2018, "Since 2010": 2010}

# Every model takes (history y, month-of-year 0-11 covering history + horizon, horizon h)
# and returns h forecasts.


def seasonal_naive(y: np.ndarray, moy: np.ndarray, h: int) -> np.ndarray:
    """Same month last year."""
    n = len(y)
    return np.array([y[n - 12 + (k % 12)] for k in range(h)])


def drift(y: np.ndarray, moy: np.ndarray, h: int) -> np.ndarray:
    """Last value, continued along the average change over the history."""
    slope = (y[-1] - y[0]) / (len(y) - 1)
    return y[-1] + slope * np.arange(1, h + 1)


def trend_season(y: np.ndarray, moy: np.ndarray, h: int, window: int | None = None) -> np.ndarray:
    """Linear trend + month-of-year effects, fitted by least squares (optionally on recent data only)."""
    n = len(y)
    start = 0 if window is None else max(0, n - window)
    t = np.arange(n + h, dtype=float)
    X = np.column_stack([np.ones(n + h), t] + [(moy[: n + h] == m).astype(float) for m in range(1, 12)])
    coef, *_ = np.linalg.lstsq(X[start:n], y[start:], rcond=None)
    return X[n:] @ coef


MODELS = {
    "Seasonal naive": seasonal_naive,
    "Drift": drift,
    "Trend + season": trend_season,
    "Trend + season (last 4 yrs)": partial(trend_season, window=48),
}


def backtest(y: np.ndarray, moy: np.ndarray, models=MODELS, horizon: int = HORIZON,
             min_train: int = MIN_TRAIN) -> dict[str, np.ndarray]:
    """Rolling-origin errors (actual - forecast), one row per origin, one column per horizon.

    NaN where the actual isn't known yet (origins near the end of the data).
    """
    n = len(y)
    origins = range(min_train, n)
    errors = {}
    for name, model in models.items():
        E = np.full((len(origins), horizon), np.nan)
        for r, o in enumerate(origins):
            h = min(horizon, n - o)
            E[r, :h] = y[o:o + h] - model(y[:o], moy[:o + h], h)
        errors[name] = E
    return errors


def crossing_year(years: np.ndarray, values: np.ndarray,
                  target: float = TARGET) -> tuple[float | None, float, float]:
    """Fit a straight line; return (year it reaches target or None if not falling, slope/year, intercept)."""
    slope, intercept = np.polyfit(years, values, 1)
    return ((target - intercept) / slope if slope < 0 else None), slope, intercept


def add_months(d: date, k: int) -> date:
    m = d.month - 1 + k
    return date(d.year + m // 12, m % 12 + 1, 1)


def main() -> None:
    with duckdb.connect(str(DB_PATH)) as con:
        rows = con.execute("SELECT month, coal_share_pct FROM marts.fct_power_mix_monthly ORDER BY month").fetchall()
        months, y = [r[0] for r in rows], np.array([r[1] for r in rows])
        future = [add_months(months[-1], k) for k in range(1, HORIZON + 1)]
        moy = np.array([d.month - 1 for d in months + future])

        # 1. Backtest every model, pick the most accurate, forecast with empirical bands
        errors = backtest(y, moy)
        mae = {name: float(np.nanmean(np.abs(E))) for name, E in errors.items()}
        best = min(mae, key=mae.get)
        fc = MODELS[best](y, moy, HORIZON)
        q025, q10, q90, q975 = np.nanquantile(errors[best], [0.025, 0.1, 0.9, 0.975], axis=0)

        # 2. Scenario: annual trend over several windows, extended to the 70% line
        annual = con.execute("""SELECT year, coal_share_pct FROM marts.fct_peer_transition_yearly
                                WHERE entity_code = 'ZAF' ORDER BY year""").fetchall()
        yrs, share = np.array([r[0] for r in annual], dtype=float), np.array([r[1] for r in annual])
        scenarios = []
        for label, start in SCENARIO_WINDOWS.items():
            mask = yrs >= start
            cross, slope, intercept = crossing_year(yrs[mask], share[mask])
            scenarios.append((label, start, int(yrs[-1]), float(slope), float(intercept), cross))

        con.execute("CREATE SCHEMA IF NOT EXISTS forecast")
        con.execute("""CREATE OR REPLACE TABLE forecast.coal_share_monthly (month DATE, kind VARCHAR, model VARCHAR,
                       coal_share_pct DOUBLE, lo80 DOUBLE, hi80 DOUBLE, lo95 DOUBLE, hi95 DOUBLE)""")
        con.executemany("INSERT INTO forecast.coal_share_monthly VALUES (?, 'actual', NULL, ?, NULL, NULL, NULL, NULL)",
                        list(zip(months, y.tolist())))
        clip = lambda a: np.clip(a, 0, 100).tolist()  # noqa: E731
        con.executemany("INSERT INTO forecast.coal_share_monthly VALUES (?, 'forecast', ?, ?, ?, ?, ?, ?)",
                        [(m, best, *vals) for m, *vals in zip(future, clip(fc), clip(fc + q10), clip(fc + q90),
                                                              clip(fc + q025), clip(fc + q975))])

        con.execute("CREATE OR REPLACE TABLE forecast.coal_share_backtest (model VARCHAR, horizon INTEGER, "
                    "mae DOUBLE, n INTEGER, is_best BOOLEAN)")
        con.executemany("INSERT INTO forecast.coal_share_backtest VALUES (?, ?, ?, ?, ?)", [
            (name, h + 1, float(np.nanmean(np.abs(E[:, h]))), int(np.sum(~np.isnan(E[:, h]))), name == best)
            for name, E in errors.items() for h in range(HORIZON)])

        # The best model's forecast path from every backtest origin, for the dashboard replay
        all_months = months + future
        con.execute("CREATE OR REPLACE TABLE forecast.coal_share_backtest_paths (origin INTEGER, "
                    "last_known DATE, month DATE, forecast DOUBLE, actual DOUBLE)")
        con.executemany("INSERT INTO forecast.coal_share_backtest_paths VALUES (?, ?, ?, ?, ?)", [
            (o, months[o - 1], all_months[o + k], float(v), float(y[o + k]) if o + k < len(y) else None)
            for o in range(MIN_TRAIN, len(y))
            for k, v in enumerate(MODELS[best](y[:o], moy[:o + HORIZON], HORIZON))])

        con.execute("CREATE OR REPLACE TABLE forecast.coal_70_scenarios (scenario VARCHAR, start_year INTEGER, "
                    "end_year INTEGER, slope_pts_per_year DOUBLE, intercept DOUBLE, crossing_year DOUBLE)")
        con.executemany("INSERT INTO forecast.coal_70_scenarios VALUES (?, ?, ?, ?, ?, ?)", scenarios)

    print("Backtest MAE (percentage points, averaged over 1-12 months ahead):")
    for name in sorted(mae, key=mae.get):
        print(f"  {'*' if name == best else ' '} {name:<28} {mae[name]:.2f}")
    print(f"Next {HORIZON} months ({best}): avg {fc.mean():.1f}% "
          f"(80% band {np.mean(fc + q10):.1f}-{np.mean(fc + q90):.1f})")
    for label, start, end, slope, _, cross in scenarios:
        when = f"{cross:.1f}" if cross else "not falling"
        print(f"  {label}: {slope:+.2f} pts/yr -> {TARGET:.0f}% in {when}")


if __name__ == "__main__":
    main()
