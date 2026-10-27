"""Shared helpers for the Streamlit pages.

The app deliberately avoids pandas, which some locked-down Windows machines block:
queries return plain lists of dicts, and charts are rendered as Vega HTML in st.iframe
because st.altair_chart / st.vega_lite_chart / st.table all import pandas internally.
"""

import altair as alt
import duckdb
import streamlit as st

from grid_pulse.charts import SERIES, SERIES_DARK
from grid_pulse.ingest import DB_PATH


def theme() -> dict:
    """Chart colors matching the viewer's Streamlit theme.

    Charts live in iframes and can't inherit Streamlit's theme, so we match it explicitly.
    Backgrounds are Streamlit's default light/dark app colors. Call per run, not at import:
    the theme belongs to the viewer's session.
    """
    if st.context.theme.type == "dark":
        return {"bg": "#0e1117", "text": "#f0efec", "muted": "#9a9a93", "grid": "#2b2d33", "series": SERIES_DARK}
    return {"bg": "#ffffff", "text": "#0b0b0b", "muted": "#a8a7a1", "grid": "#e4e3df", "series": SERIES}


@st.cache_data
def query(sql: str, params: tuple = ()) -> list[dict]:
    with duckdb.connect(str(DB_PATH), read_only=True) as con:
        cur = con.execute(sql, list(params))
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def require_data() -> None:
    if not DB_PATH.exists():
        st.error("No data yet. Run `python -m grid_pulse.ingest` then `python -m grid_pulse.transform`.")
        st.stop()


def style(chart: alt.TopLevelMixin, height: int) -> alt.TopLevelMixin:
    T = theme()
    return (
        chart.properties(height=height, width="container", background=T["bg"])
        .configure_view(stroke=None)
        .configure_axis(labelColor=T["muted"], titleColor=T["muted"], gridColor=T["grid"], domainColor=T["grid"],
                        tickColor=T["grid"], labelFontSize=11, titleFontWeight="normal")
        .configure_axisX(grid=False)
        .configure_legend(labelColor=T["text"], labelFontSize=12)
    )


def show(chart: alt.TopLevelMixin, height: int, key: str, pad: int = 60) -> None:
    """pad: room for axis labels around the plot; raise it for charts with a top legend."""
    # Vega needs its own page (inline in Streamlit's DOM it fails to load), so each chart
    # gets an iframe. The HTML is Altair's own embed code over our own data, never user input.
    st.iframe(style(chart, height).to_html(output_div=key), height=height + pad)
