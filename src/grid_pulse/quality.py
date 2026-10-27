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
}


def run_checks(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    """Return {check name: offending row count} for every failing check."""
    failures = {}
    for name, sql in CHECKS.items():
        n = con.execute(f"SELECT count(*) FROM ({sql})").fetchone()[0]
        if n:
            failures[name] = n
    return failures
