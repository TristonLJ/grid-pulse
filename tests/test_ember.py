import json

import duckdb
import pytest

from grid_pulse import ember
from grid_pulse.ingest import load_json


def test_load_json_creates_raw_table(tmp_path):
    rows = [
        {"entity_code": "ZAF", "date": "2024-01-01", "series": "Coal", "generation_twh": 15.2},
        {"entity_code": "ZAF", "date": "2024-02-01", "series": "Coal", "generation_twh": 14.1},
    ]
    path = tmp_path / "gen.json"
    path.write_text(json.dumps(rows))

    with duckdb.connect() as con:
        assert load_json(con, "gen", path) == 2
        assert con.execute("SELECT typeof(date) FROM raw.gen LIMIT 1").fetchone()[0] == "DATE"


def test_missing_api_key_raises(monkeypatch):
    monkeypatch.delenv("EMBER_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="EMBER_API_KEY"):
        ember.generation_monthly()
