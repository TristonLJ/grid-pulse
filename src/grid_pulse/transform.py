"""Build the staging and marts tables from raw, then run data-quality checks.

Each file sql/<schema>/<name>.sql becomes the table <schema>.<name>.
Schemas build in LAYERS order, so marts can depend on staging.

Usage:  python -m grid_pulse.transform
"""

import sys
from pathlib import Path

import duckdb

from grid_pulse.ingest import DB_PATH
from grid_pulse.quality import run_checks

SQL_DIR = Path(__file__).resolve().parents[2] / "sql"
LAYERS = ["staging", "marts"]


def build(con: duckdb.DuckDBPyConnection) -> list[str]:
    built = []
    for layer in LAYERS:
        con.execute(f"CREATE SCHEMA IF NOT EXISTS {layer}")
        for path in sorted((SQL_DIR / layer).glob("*.sql")):
            table = f"{layer}.{path.stem}"
            con.execute(f"CREATE OR REPLACE TABLE {table} AS {path.read_text(encoding='utf-8')}")
            built.append(table)
    return built


def main() -> None:
    with duckdb.connect(str(DB_PATH)) as con:
        for table in build(con):
            print(f"built {table}: {con.execute(f'SELECT count(*) FROM {table}').fetchone()[0]:,} rows")
        failures = run_checks(con)

    if failures:
        for name, n in failures.items():
            print(f"FAIL {name}: {n} offending rows")
        sys.exit(1)
    print("all quality checks passed")


if __name__ == "__main__":
    main()
