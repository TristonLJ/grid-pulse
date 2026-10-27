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
python -m grid_pulse.ingest      # API -> data/raw -> raw.* tables
python -m grid_pulse.transform   # raw -> staging -> marts, then data-quality checks
pytest
```

**Dashboard:** `streamlit run streamlit_app.py` opens an interactive dashboard at http://localhost:8501.
It has a year filter, KPIs, an animated replay of the power mix month by month, and hover tooltips on every chart.

**Optional: explore in MySQL.** DuckDB (`data/grid.duckdb`) is the project's database and needs no server.
To browse the results in MySQL Workbench, set the `MYSQL_*` values in `.env` and run
`python -m grid_pulse.export_mysql`. That copies the staging and mart tables into a `grid_pulse` database.

## Roadmap

- [x] Project setup
- [x] Ember ingestion → DuckDB
- [ ] Eskom hourly CSV loader
- [x] Clean / tidy SQL models + data-quality tests
- [x] Notebook 01: power mix 2018–2025
- [ ] Notebook 02: Eskom hourly demand vs. capacity, outages
- [ ] Demand forecasting (baseline vs. gradient boosting, backtested)
- [x] Streamlit dashboard with animated month-by-month replay
- [ ] GitHub Actions scheduled refresh

## Key findings so far

From [notebook 01](notebooks/01_power_mix.ipynb) (Ember monthly data, full years 2018–2025):

1. **Coal is losing share steadily, but slowly:** from 90.9% of generation in 2018 to 80.3% in 2025.
2. **Solar is the growth story:** utility-scale solar went up 4.3x (4.3 → 18.6 TWh); wind + solar now provide ≈13% of generation.
3. **2023 was the low point:** domestic generation fell 12% from 2018, then partly recovered in 2024.

![Coal share](reports/figures/01_coal_share.png)
![Wind and solar](reports/figures/02_wind_solar.png)
![Generation](reports/figures/03_generation.png)
