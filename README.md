# grid-pulse ⚡

Analysis of South Africa's electricity grid: demand vs. available capacity, unplanned outages,
the coal-to-renewables shift, and short-term demand forecasting.

> 🚧 Work in progress, built as a learning project.

## Data sources

| Source | Granularity | How it's loaded |
|---|---|---|
| [Ember API](https://ember-energy.org/data/api/) | Monthly generation by fuel, demand | `python -m grid_pulse.ingest` (automated) |
| [Eskom Data Portal](https://www.eskom.co.za/dataportal/) | Hourly demand, capacity, outages, renewables | Bulk CSVs via the data request form → `data/raw/eskom/` |

## Quickstart

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (source .venv/bin/activate on macOS/Linux)
pip install -e ".[dev]"
copy .env.example .env          # then paste your Ember API key
python -m grid_pulse.ingest
pytest
```

## Roadmap

- [x] Project setup
- [x] Ember ingestion → DuckDB
- [ ] Eskom hourly CSV loader
- [ ] Clean / tidy SQL models + data-quality tests
- [ ] Exploratory analysis notebooks
- [ ] Demand forecasting (baseline vs. gradient boosting, backtested)
- [ ] Streamlit dashboard
- [ ] GitHub Actions scheduled refresh

## Key findings

_Coming soon._
