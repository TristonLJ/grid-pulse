"""Optional: copy the built staging + marts tables from DuckDB into a MySQL/MariaDB database.

DuckDB stays the source of truth; this is for exploring the results in MySQL Workbench.
Connection settings come from .env (see .env.example). The database is created if missing,
and each exported table is dropped and recreated, so re-running is safe.

Usage:  python -m grid_pulse.export_mysql
"""

import os

import duckdb
from dotenv import load_dotenv

from grid_pulse.ingest import DB_PATH, ROOT
from grid_pulse.transform import LAYERS


def mysql_dsn(database: str) -> str:
    parts = {
        "host": os.environ.get("MYSQL_HOST", "127.0.0.1"),
        "port": os.environ.get("MYSQL_PORT", "3306"),
        "user": os.environ.get("MYSQL_USER", "root"),
        "password": os.environ.get("MYSQL_PASSWORD", ""),
        "database": database,
    }
    # DuckDB's DSN parser rejects empty values (e.g. XAMPP's blank root password), so omit them
    return " ".join(f"{k}={v}" for k, v in parts.items() if v)


def main() -> None:
    load_dotenv(ROOT / ".env")
    database = os.environ.get("MYSQL_DATABASE", "grid_pulse")

    # In-memory session with the warehouse attached read-only. (Opening the file itself with
    # read_only=True would make the MySQL attachment read-only too.)
    with duckdb.connect() as con:
        con.execute("ATTACH ? AS grid (READ_ONLY)", [str(DB_PATH)])
        con.execute("INSTALL mysql")
        con.execute("LOAD mysql")

        # Connect via the always-present `mysql` system DB to create ours. (An empty database
        # isn't an option: the extension would fall back to the MYSQL_DATABASE env var.)
        con.execute("ATTACH ? AS server (TYPE mysql)", [mysql_dsn("mysql")])
        con.execute("CALL mysql_execute('server', ?)", [f"CREATE DATABASE IF NOT EXISTS `{database}`"])
        con.execute("DETACH server")

        con.execute("ATTACH ? AS my (TYPE mysql)", [mysql_dsn(database)])
        tables = con.execute(
            "SELECT schema_name, table_name FROM duckdb_tables() WHERE database_name = 'grid' "
            "AND schema_name IN (SELECT unnest(?)) ORDER BY schema_name, table_name",
            [LAYERS],
        ).fetchall()
        for schema, table in tables:
            con.execute(f"DROP TABLE IF EXISTS my.{table}")
            con.execute(f"CREATE TABLE my.{table} AS SELECT * FROM grid.{schema}.{table}")
            n = con.execute(f"SELECT count(*) FROM my.{table}").fetchone()[0]
            print(f"{database}.{table}: {n:,} rows")


if __name__ == "__main__":
    main()
