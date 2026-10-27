"""Data-quality checks. Each check is a query returning the offending rows; zero rows = pass."""

import duckdb

# Ember rounds to 2 decimals, so sums can drift by a few hundredths of a TWh.
TOLERANCE_TWH = 0.05

CHECKS = {
    "generation: one row per month per fuel": """
        select month, fuel from staging.stg_generation_monthly
        group by all having count(*) > 1
    """,
    "generation: no negative output (net imports excepted)": """
        select * from staging.stg_generation_monthly
        where generation_twh < 0 and fuel_group <> 'Imports'
    """,
    "generation: fuels sum to Ember's reported total": f"""
        select r.date
        from raw.ember_generation_monthly r
        join marts.fct_power_mix_monthly m on m.month = r.date
        where r.series = 'Total generation'
          and abs(r.generation_twh - m.generation_twh) > {TOLERANCE_TWH}
    """,
    "mix: generation + net imports = demand": f"""
        select month from marts.fct_power_mix_monthly
        where demand_twh is null
           or abs(generation_twh + net_imports_twh - demand_twh) > {TOLERANCE_TWH}
    """,
    "mix: no missing months": """
        select month from marts.fct_power_mix_monthly
        qualify month <> lag(month) over (order by month) + interval 1 month
    """,
    "yearly: one row per entity per year per fuel": """
        select entity, year, fuel from staging.stg_generation_yearly
        group by all having count(*) > 1
    """,
    "yearly: fuels sum to Ember's reported total": f"""
        select r.entity, r.date
        from raw.ember_generation_yearly r
        join marts.fct_peer_transition_yearly m on m.entity = r.entity and m.year = cast(r.date as integer)
        where r.series = 'Total generation'
          and abs(r.generation_twh - m.generation_twh) > {TOLERANCE_TWH}
    """,
    "yearly: every entity covers every year": """
        select entity from marts.fct_peer_transition_yearly
        group by entity
        having count(distinct year) < (select count(distinct year) from marts.fct_peer_transition_yearly)
    """,
    # Coal plants emit roughly 0.8-1.2 kg CO2/kWh; far outside that means a unit or join bug
    "co2: coal emission rate is physically plausible": """
        select year from marts.fct_co2_avoided_yearly
        where coal_mt_per_twh not between 0.6 and 1.3
    """,
}


def run_checks(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    """Return {check name: offending row count} for every failing check."""
    failures = {}
    for name, sql in CHECKS.items():
        n = con.execute(f"SELECT count(*) FROM ({sql})").fetchone()[0]
        if n:
            failures[name] = n
    return failures
