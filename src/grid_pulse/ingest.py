"""Pull Ember data into a local DuckDB warehouse.

Raw API responses land as JSON in data/raw/ember/, then load into the `raw` schema.

Usage:  python -m grid_pulse.ingest
"""

import json
from functools import partial
from pathlib import Path

import duckdb
from dotenv import load_dotenv

from grid_pulse import ember

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw" / "ember"
DB_PATH = ROOT / "data" / "grid.duckdb"

# Peers for the international comparison: sunny, coal-heavy or emerging economies like SA's
PEER_CODES = ["ZAF", "CHL", "BRA", "MAR", "EGY", "KEN", "IND", "VNM", "IDN", "AUS", "MEX", "TUR"]
BENCHMARKS = ["World", "Africa"]


def load_json(con: duckdb.DuckDBPyConnection, table: str, path: Path) -> int:
    con.execute("CREATE SCHEMA IF NOT EXISTS raw")
    con.execute(f"CREATE OR REPLACE TABLE raw.{table} AS SELECT * FROM read_json_auto(?)", [str(path)])
    return con.execute(f"SELECT count(*) FROM raw.{table}").fetchone()[0]


def main() -> None:
    load_dotenv(ROOT / ".env")
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    peers = partial(ember.yearly, codes=PEER_CODES, regions=BENCHMARKS)
    fetches = {
        "ember_generation_monthly": ember.generation_monthly,
        "ember_demand_monthly": ember.demand_monthly,
        "ember_generation_yearly": partial(peers, "electricity-generation"),
        "ember_emissions_yearly": partial(peers, "power-sector-emissions"),
        "ember_carbon_intensity_yearly": partial(peers, "carbon-intensity"),
    }

    with duckdb.connect(str(DB_PATH)) as con:
        for table, fetch in fetches.items():
            path = RAW_DIR / f"{table}.json"
            path.write_text(json.dumps(fetch()), encoding="utf-8")
            print(f"raw.{table}: {load_json(con, table, path):,} rows")


if __name__ == "__main__":
    main()
