import duckdb
import pytest

from grid_pulse.quality import run_checks
from grid_pulse.transform import build

GENERATION = [
    # month, series, is_aggregate, twh
    ("2024-01-01", "Coal", False, 15.0),
    ("2024-01-01", "Wind", False, 1.0),
    ("2024-01-01", "Net imports", False, 0.5),
    ("2024-01-01", "Total generation", True, 16.0),
    ("2024-02-01", "Coal", False, 14.0),
    ("2024-02-01", "Wind", False, 1.5),
    ("2024-02-01", "Net imports", False, 0.5),
    ("2024-02-01", "Total generation", True, 15.5),
]
DEMAND = [("2024-01-01", 16.5), ("2024-02-01", 16.0)]


@pytest.fixture
def con():
    con = duckdb.connect()
    con.execute("CREATE SCHEMA raw")
    con.execute("""CREATE TABLE raw.ember_generation_monthly (entity_code VARCHAR, date DATE, series VARCHAR,
                   is_aggregate_series BOOLEAN, generation_twh DOUBLE, share_of_generation_pct DOUBLE)""")
    con.execute("CREATE TABLE raw.ember_demand_monthly (entity_code VARCHAR, date DATE, demand_twh DOUBLE)")
    con.executemany("INSERT INTO raw.ember_generation_monthly VALUES ('ZAF', ?, ?, ?, ?, NULL)", GENERATION)
    con.executemany("INSERT INTO raw.ember_demand_monthly VALUES ('ZAF', ?, ?)", DEMAND)
    yield con
    con.close()


def test_mart_excludes_aggregates_and_imports(con):
    build(con)
    row = con.execute("""SELECT generation_twh, coal_share_pct, wind_solar_twh
                         FROM marts.fct_power_mix_monthly WHERE month = '2024-01-01'""").fetchone()
    assert row == (16.0, 93.75, 1.0)


def test_clean_data_passes_checks(con):
    build(con)
    assert run_checks(con) == {}


def test_demand_mismatch_is_caught(con):
    con.execute("UPDATE raw.ember_demand_monthly SET demand_twh = 20 WHERE date = '2024-02-01'")
    build(con)
    assert run_checks(con) == {"mix: generation + net imports = demand": 1}


def test_missing_month_is_caught(con):
    con.execute("INSERT INTO raw.ember_generation_monthly VALUES ('ZAF', '2024-04-01', 'Coal', false, 14, NULL)")
    con.execute("INSERT INTO raw.ember_demand_monthly VALUES ('ZAF', '2024-04-01', 14)")
    build(con)
    assert "mix: no missing months" in run_checks(con)
