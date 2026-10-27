from datetime import date

import numpy as np
import pytest

from grid_pulse.forecast import add_months, backtest, crossing_year, seasonal_naive, trend_season

SEASON = np.array([3, 1, 0, -1, -2, -3, -2, -1, 0, 1, 2, 2], dtype=float)


def synthetic(n: int) -> tuple[np.ndarray, np.ndarray]:
    """90% falling 0.1 pts/month, plus a fixed seasonal pattern."""
    t = np.arange(n)
    return 90 - 0.1 * t + SEASON[t % 12], t % 12


def test_trend_season_recovers_exact_pattern():
    y, moy = synthetic(72)
    full, moy_full = synthetic(84)
    assert trend_season(y, moy_full, 12) == pytest.approx(full[72:])


def test_seasonal_naive_repeats_last_year():
    y = np.arange(24, dtype=float)
    assert seasonal_naive(y, None, 14).tolist() == list(range(12, 24)) + [12, 13]


def test_backtest_marks_unknown_actuals_as_nan():
    y, moy = synthetic(60)
    E = backtest(y, np.concatenate([moy, np.arange(12)]), models={"t": trend_season}, min_train=50)["t"]
    assert E.shape == (10, 12)
    assert np.isnan(E[-1, 1:]).all() and not np.isnan(E[-1, 0])   # last origin: only 1 month known
    assert np.nanmax(np.abs(E)) == pytest.approx(0, abs=1e-9)      # perfect model -> zero error


def test_crossing_year():
    cross, slope, intercept = crossing_year(np.array([2020, 2021, 2022]), np.array([80.0, 79.0, 78.0]))
    assert slope == pytest.approx(-1)
    assert intercept + slope * 2030 == pytest.approx(70)
    assert cross == pytest.approx(2030)
    assert crossing_year(np.array([2020, 2021]), np.array([80.0, 81.0]))[0] is None


def test_add_months_rolls_over_year():
    assert add_months(date(2026, 8, 1), 5) == date(2027, 1, 1)
