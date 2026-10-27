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

# One SA year: 100 TWh coal emitting 90 Mt (0.9 Mt/TWh), 20 TWh wind + solar, grid at 800 g/kWh
YEARLY_GENERATION = [
    ("Coal", False, 100.0),
    ("Wind", False, 10.0),
    ("Solar", False, 10.0),
    ("Total generation", True, 120.0),
]
YEARLY_EMISSIONS = [("Coal", False, 90.0), ("Wind", False, 0.0), ("Solar", False, 0.0)]


@pytest.fixture
def con():
    con = duckdb.connect()
    con.execute("CREATE SCHEMA raw")
    con.execute("""CREATE TABLE raw.ember_generation_monthly (entity_code VARCHAR, date DATE, series VARCHAR,
                   is_aggregate_series BOOLEAN, generation_twh DOUBLE, share_of_generation_pct DOUBLE)""")
    con.execute("CREATE TABLE raw.ember_demand_monthly (entity_code VARCHAR, date DATE, demand_twh DOUBLE)")
    con.execute("""CREATE TABLE raw.ember_generation_yearly (entity VARCHAR, entity_code VARCHAR,
                   is_aggregate_entity BOOLEAN, date VARCHAR, series VARCHAR, is_aggregate_series BOOLEAN,
                   generation_twh DOUBLE)""")
    con.execute("""CREATE TABLE raw.ember_emissions_yearly (entity VARCHAR, date VARCHAR, series VARCHAR,
                   is_aggregate_series BOOLEAN, emissions_mtco2 DOUBLE)""")
    con.execute("""CREATE TABLE raw.ember_carbon_intensity_yearly (entity VARCHAR, date VARCHAR,
                   emissions_intensity_gco2_per_kwh DOUBLE)""")

    con.executemany("INSERT INTO raw.ember_generation_monthly VALUES ('ZAF', ?, ?, ?, ?, NULL)", GENERATION)
    con.executemany("INSERT INTO raw.ember_demand_monthly VALUES ('ZAF', ?, ?)", DEMAND)
    con.executemany("INSERT INTO raw.ember_generation_yearly VALUES ('South Africa', 'ZAF', false, '2024', ?, ?, ?)",
                    YEARLY_GENERATION)
    con.executemany("INSERT INTO raw.ember_emissions_yearly VALUES ('South Africa', '2024', ?, ?, ?)", YEARLY_EMISSIONS)
    con.execute("INSERT INTO raw.ember_carbon_intensity_yearly VALUES ('South Africa', '2024', 800)")
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


def test_co2_avoided_brackets(con):
    build(con)
    high, low, cf = con.execute("""SELECT avoided_high_mtco2, avoided_low_mtco2, counterfactual_gco2_per_kwh
                                   FROM marts.fct_co2_avoided_yearly WHERE year = 2024""").fetchone()
    assert high == pytest.approx(20 * 0.9)   # wind+solar TWh x coal Mt/TWh
    assert low == pytest.approx(20 * 0.8)    # wind+solar TWh x grid g/kWh / 1000
    assert cf == pytest.approx(1000 * (90 + 18) / 120)


def test_implausible_coal_rate_is_caught(con):
    con.execute("UPDATE raw.ember_emissions_yearly SET emissions_mtco2 = 90000 WHERE series = 'Coal'")  # kt, not Mt
    build(con)
    assert "co2: coal emission rate is physically plausible" in run_checks(con)
