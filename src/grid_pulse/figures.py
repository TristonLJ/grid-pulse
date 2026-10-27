"""Render the static README figures (04-06) from the warehouse.

Figures 01-03 come from notebooks/01_power_mix.ipynb. These three cover the peer
comparison, CO2 avoided and the forecast, which otherwise live only in the dashboard.

Usage:  python -m grid_pulse.figures   (after ingest, transform and forecast)
"""

import duckdb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FuncFormatter, MultipleLocator  # noqa: E402

from grid_pulse.charts import SERIES, TEXT, TEXT_SECONDARY, apply_style, save  # noqa: E402
from grid_pulse.ingest import DB_PATH  # noqa: E402

MUTED = "#a8a7a1"
pct = FuncFormatter(lambda v, _: f"{v:.0f}%")


def peers(con: duckdb.DuckDBPyConnection) -> None:
    year = con.execute("SELECT max(year) FROM marts.fct_peer_transition_yearly").fetchone()[0]
    rows = con.execute("""SELECT entity, is_benchmark, wind_solar_share_pct FROM marts.fct_peer_transition_yearly
                          WHERE year = ? ORDER BY wind_solar_share_pct""", [year]).fetchall()
    fig, ax = plt.subplots(figsize=(8, 5.2))
    colors = [SERIES[0] if e == "South Africa" else SERIES[1] if bench else MUTED for e, bench, _ in rows]
    ax.barh([r[0] for r in rows], [r[2] for r in rows], color=colors, height=0.7)
    for i, (e, _, v) in enumerate(rows):
        ax.text(v + 0.4, i, f"{v:.1f}%", va="center", fontweight="bold" if e == "South Africa" else "normal")
    ax.xaxis.set_major_formatter(pct)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", visible=True)
    ax.set_xlim(0, max(r[2] for r in rows) * 1.12)
    ax.set_title(f"SA trails most peers on wind + solar share of generation ({year})")
    ax.text(0, -0.13, "Blue: South Africa · Orange: World and Africa totals · Grey: peer countries",
            transform=ax.transAxes, color=TEXT_SECONDARY, fontsize=9)
    save(fig, "04_peers")
    plt.close(fig)


def co2(con: duckdb.DuckDBPyConnection) -> None:
    rows = con.execute("""SELECT year, avoided_low_mtco2, avoided_high_mtco2 FROM marts.fct_co2_avoided_yearly
                          WHERE year >= 2012 ORDER BY year""").fetchall()
    years, low, high = map(list, zip(*rows))
    fig, ax = plt.subplots()
    ax.bar(years, high, color=SERIES[0], alpha=0.35, label="Up to (if it replaced coal power)")
    ax.bar(years, low, color=SERIES[0], label="At least (if it replaced average grid power)")
    ax.annotate(f"{low[-1]:.1f}–{high[-1]:.1f} Mt", (years[-1], high[-1]), textcoords="offset points",
                xytext=(0, 6), ha="center", fontweight="bold", color=TEXT)
    ax.set_xticks(years[::2])
    ax.set_ylim(0, max(high) * 1.15)  # headroom so the label clears the title
    ax.set_ylabel("Mt CO₂ per year")
    ax.set_title("CO₂ kept out of the air by SA's wind and solar")
    ax.legend(loc="upper left")
    save(fig, "05_co2_avoided")
    plt.close(fig)


def forecast(con: duckdb.DuckDBPyConnection) -> None:
    rows = con.execute("""SELECT month, kind, coal_share_pct, lo80, hi80, lo95, hi95 FROM forecast.coal_share_monthly
                          WHERE month >= '2022-01-01' ORDER BY month""").fetchall()
    act = [r for r in rows if r[1] == "actual"]
    fc = [act[-1][:3] + (act[-1][2],) * 4] + [r for r in rows if r[1] == "forecast"]
    fig, ax = plt.subplots()
    fx = [r[0] for r in fc]
    ax.fill_between(fx, [r[5] for r in fc], [r[6] for r in fc], color=SERIES[0], alpha=0.15, linewidth=0,
                    label="95% range")
    ax.fill_between(fx, [r[3] for r in fc], [r[4] for r in fc], color=SERIES[0], alpha=0.3, linewidth=0,
                    label="80% range")
    ax.plot([r[0] for r in act], [r[2] for r in act], color=TEXT, linewidth=1.5, label="Actual")
    ax.plot(fx, [r[2] for r in fc], color=SERIES[0], linestyle="--", label="Forecast")
    ax.yaxis.set_major_locator(MultipleLocator(5))
    ax.yaxis.set_major_formatter(pct)
    ax.set_title("Coal share: next 12 months, with ranges from past forecast errors")
    ax.legend(loc="lower left", ncols=2)
    save(fig, "06_forecast")
    plt.close(fig)


def main() -> None:
    apply_style()
    with duckdb.connect(str(DB_PATH), read_only=True) as con:
        for render in (peers, co2, forecast):
            render(con)
            print(f"rendered {render.__name__}")


if __name__ == "__main__":
    main()
