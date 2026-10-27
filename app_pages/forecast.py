"""Page: forecasting SA's coal share (next 12 months) and a when-below-70% scenario."""

import altair as alt
import streamlit as st

from grid_pulse.dash import query, require_data, show, style, theme
from grid_pulse.forecast import HORIZON, MIN_TRAIN, TARGET
from grid_pulse.replay import replay_html

T = theme()
require_data()

try:
    series = query("SELECT strftime(month, '%Y-%m-%d') AS month, * EXCLUDE (month) "
                   "FROM forecast.coal_share_monthly ORDER BY month")
except Exception:  # duckdb.CatalogException: forecast tables not built yet
    st.error("No forecast yet. Run `python -m grid_pulse.forecast`.")
    st.stop()
bt = query("SELECT * FROM forecast.coal_share_backtest ORDER BY model, horizon")
paths = query("SELECT origin, strftime(last_known, '%b %Y') AS last_known, strftime(month, '%Y-%m-%d') AS month, "
              "forecast, actual FROM forecast.coal_share_backtest_paths ORDER BY origin, month")
scen = query("SELECT * FROM forecast.coal_70_scenarios ORDER BY crossing_year")
annual = query("SELECT year, coal_share_pct FROM marts.fct_peer_transition_yearly "
               "WHERE entity_code = 'ZAF' ORDER BY year")

actual = [r for r in series if r["kind"] == "actual"]
fc = [r for r in series if r["kind"] == "forecast"]
best = fc[0]["model"]
mae = {m: sum(r["mae"] for r in bt if r["model"] == m) / HORIZON for m in {r["model"] for r in bt}}
naive = mae["Seasonal naive"]
crossings = [s["crossing_year"] for s in scen if s["crossing_year"]]

st.title("📈 Will coal's share keep falling?")
st.caption("A 12-month forecast of SA's monthly coal share, tested against history, plus a longer-run "
           f"scenario for when coal could fall below {TARGET:.0f}%.")

k1, k2, k3 = st.columns(3)
avg = lambda key: sum(r[key] for r in fc) / len(fc)  # noqa: E731
k1.metric(f"Coal share, next {HORIZON} months (avg)", f"{avg('coal_share_pct'):.1f}%",
          help=f"80% range {avg('lo80'):.1f}–{avg('hi80'):.1f}%. Model: {best}.")
k2.metric("Forecast error (backtested)", f"±{mae[best]:.1f} pts",
          f"{100 * (1 - mae[best] / naive):.0f}% better than naive", delta_color="normal",
          help="Mean absolute error, 1–12 months ahead, vs. 'same month last year'.")
k3.metric(f"Coal below {TARGET:.0f}% (scenario)", f"~{min(crossings):.0f}–{max(crossings):.0f}",
          help="If the annual trend fitted over different windows continues. A scenario, not a forecast.")

# --- Forecast with bands ------------------------------------------------------------
st.subheader(f"Next {HORIZON} months")
recent = [r for r in actual if r["month"] >= "2022-01-01"]
bridge = [{**actual[-1], "lo80": actual[-1]["coal_share_pct"], "hi80": actual[-1]["coal_share_pct"],
           "lo95": actual[-1]["coal_share_pct"], "hi95": actual[-1]["coal_share_pct"]}]
band_rows = bridge + fc
x = alt.X("month:T", title=None, axis=alt.Axis(format="%Y", tickCount="year"))
band95 = alt.Chart(alt.Data(values=band_rows)).mark_area(color=T["series"][0], opacity=0.15).encode(
    x=x, y=alt.Y("lo95:Q", title="Coal share of generation (%)", scale=alt.Scale(zero=False)), y2="hi95:Q")
band80 = alt.Chart(alt.Data(values=band_rows)).mark_area(color=T["series"][0], opacity=0.3).encode(
    x=x, y="lo80:Q", y2="hi80:Q")
hist = alt.Chart(alt.Data(values=recent)).mark_line(color=T["text"], strokeWidth=1.5).encode(x=x, y="coal_share_pct:Q")
fline = alt.Chart(alt.Data(values=bridge + fc)).mark_line(color=T["series"][0], strokeWidth=2,
                                                          strokeDash=[5, 3]).encode(x=x, y="coal_share_pct:Q")
tips = alt.Chart(alt.Data(values=recent + fc)).mark_circle(size=70, opacity=0).encode(
    x=x, y="coal_share_pct:Q",
    tooltip=[alt.Tooltip("month:T", title="Month", format="%b %Y"), alt.Tooltip("kind:N", title=""),
             alt.Tooltip("coal_share_pct:Q", title="Coal %", format=".1f"),
             alt.Tooltip("lo80:Q", title="80% low", format=".1f"), alt.Tooltip("hi80:Q", title="80% high", format=".1f")])
show(band95 + band80 + hist + fline + tips, 320, "forecast")
st.caption("Solid: actual · Dashed: forecast · Shaded: 80% and 95% ranges, taken from the model's own past errors.")

st.info(
    f"**Honest result:** the best model ({best}) is only {100 * (1 - mae[best] / naive):.0f}% more accurate than "
    f"simply repeating the same month last year ({mae[best]:.2f} vs {naive:.2f} points). Month to month, SA's coal "
    "share is driven mostly by noise like plant breakdowns, weather and demand swings, not by a smooth trend. "
    "The trend is real over years, but it barely shows over a few months."
)

# --- Backtest replay ----------------------------------------------------------------
st.subheader("How the model was tested")
idx_actual = [{"i": i, "month": r["month"], "v": r["coal_share_pct"]} for i, r in enumerate(actual)]
origins = sorted({p["origin"] for p in paths})
frames = []
for o in origins:
    known = [p for p in paths if p["origin"] == o and p["actual"] is not None]
    err = sum(abs(p["forecast"] - p["actual"]) for p in known) / len(known)
    frames.append({"label": f"Made after {next(p['last_known'] for p in paths if p['origin'] == o)}",
                   "stats": {"Months checked": f"{len(known)}", "Avg error": f"{err:.1f} pts"}})
path_rows = [{**p, "t": p["origin"] - MIN_TRAIN} for p in paths]

t = alt.param(name="t", value=0)
bx = alt.X("month:T", title=None, axis=alt.Axis(format="%Y", tickCount="year"),
           scale=alt.Scale(domain=[actual[0]["month"], fc[-1]["month"]]))
by_ = alt.Y("v:Q", title="Coal share (%)", scale=alt.Scale(domain=[66, 96]))
truth = alt.Chart(alt.Data(values=idx_actual)).mark_line(color=T["muted"], strokeWidth=1).encode(x=bx, y=by_)
known_line = alt.Chart(alt.Data(values=idx_actual)).transform_filter(f"datum.i < t + {MIN_TRAIN}").mark_line(
    color=T["text"], strokeWidth=2).encode(x=bx, y=by_)
path = alt.Chart(alt.Data(values=path_rows)).transform_filter("datum.t == t").transform_calculate(
    v="datum.forecast").mark_line(color=T["series"][0], strokeWidth=2.5, point=True).encode(x=bx, y=by_)
replay = (truth + known_line + path).add_params(t)

st.iframe(replay_html(style(replay, 300).to_dict(), frames, T, interval_ms=180), height=430)
st.caption("White: what the model knew · Blue: its 12-month forecast from that point · Grey: what actually happened. "
           "Press play to step through every forecast made since "
           f"{frames[0]['label'].removeprefix('Made after ')}.")

left, right = st.columns(2)

with left:
    st.subheader("Error by forecast distance")
    order = sorted(mae, key=mae.get)
    err_rows = [{**r, "best": r["model"] == best} for r in bt]
    lines = alt.Chart(alt.Data(values=err_rows)).mark_line(point=True).encode(
        x=alt.X("horizon:O", title="Months ahead", axis=alt.Axis(labelAngle=0)),
        y=alt.Y("mae:Q", title="Mean absolute error (pts)"),
        color=alt.Color("model:N", title=None, sort=order, scale=alt.Scale(domain=order, range=[
            *T["series"], T["muted"]][: len(order)]), legend=alt.Legend(orient="top", columns=2)),
        strokeWidth=alt.condition("datum.best", alt.value(3), alt.value(1.5)),
        tooltip=[alt.Tooltip("model:N"), alt.Tooltip("horizon:O", title="Months ahead"),
                 alt.Tooltip("mae:Q", title="MAE", format=".2f"), alt.Tooltip("n:Q", title="Forecasts scored")],
    )
    show(lines, 300, "errors", pad=110)
    # The two findings that hold up: who wins one month out, and how close the rest are beyond that
    err = {(r["model"], r["horizon"]): r["mae"] for r in bt}
    h1 = min(mae, key=lambda m: err[(m, 1)])
    gap = max(abs(err[(best, h)] - err[("Seasonal naive", h)]) for h in range(2, HORIZON + 1))
    st.caption("Lower is better. Every model was scored on the same forecasts made since "
               f"{frames[0]['label'].removeprefix('Made after ')}. **One month ahead, {h1} wins** "
               f"({err[(h1, 1)]:.1f} pts). Further out, {best} and the seasonal baseline stay within "
               f"{gap:.1f} pts of each other.")

with right:
    st.subheader(f"When could coal fall below {TARGET:.0f}%?")
    end = int(max(crossings)) + 2
    # Each window's fitted trend, drawn from its first year, so you can see what it was fitted on
    proj = [{"scenario": s["scenario"], "year": yr, "v": s["intercept"] + s["slope_pts_per_year"] * yr}
            for s in scen for yr in (s["start_year"], end)]
    sc_order = [s["scenario"] for s in scen]
    act = alt.Chart(alt.Data(values=annual)).mark_line(color=T["text"], strokeWidth=2).encode(
        x=alt.X("year:Q", title=None, axis=alt.Axis(format="d"), scale=alt.Scale(domain=[2000, end])),
        y=alt.Y("coal_share_pct:Q", title="Coal share (%)", scale=alt.Scale(domain=[60, 100])))
    proj_lines = alt.Chart(alt.Data(values=proj)).mark_line(strokeDash=[5, 3], strokeWidth=2).encode(
        x="year:Q", y="v:Q",
        color=alt.Color("scenario:N", title=None, sort=sc_order,
                        scale=alt.Scale(domain=sc_order, range=T["series"][: len(sc_order)]),
                        legend=alt.Legend(orient="top")))
    rule = alt.Chart(alt.Data(values=[{"y": TARGET}])).mark_rule(color=T["muted"], strokeDash=[2, 2]).encode(y="y:Q")
    marks = alt.Chart(alt.Data(values=[{"scenario": s["scenario"], "year": s["crossing_year"], "v": TARGET,
                                        "label": f"{s['crossing_year']:.0f}"} for s in scen if s["crossing_year"]]))
    dots = marks.mark_point(filled=True, size=70).encode(
        x="year:Q", y="v:Q", color=alt.Color("scenario:N", sort=sc_order, legend=None,
                                             scale=alt.Scale(domain=sc_order, range=T["series"][: len(sc_order)])),
        tooltip=[alt.Tooltip("scenario:N", title="Trend"), alt.Tooltip("year:Q", title="Reaches 70%", format=".1f")])
    dot_labels = marks.mark_text(dy=14, color=T["text"]).encode(x="year:Q", y="v:Q", text="label:N")
    show(act + proj_lines + rule + dots + dot_labels, 300, "scenario", pad=95)
    st.caption("Dashed: straight-line trends fitted to annual coal share over three windows, starting from "
               "each window's first year. The spread shows how much the answer depends on which years you trust.")

with st.expander("Method and caveats"):
    st.markdown(f"""
- **Models compared:** same month last year (seasonal naive); a straight line from the first to the last value
  (drift); and a linear trend + month-of-year regression, fitted on all history or on the last 4 years only.
- **Backtest:** from month {MIN_TRAIN} onward, each model saw only the data up to that month and forecast the
  next {HORIZON}. Scores are mean absolute errors against what actually happened.
- **Ranges** are the 10th–90th and 2.5th–97.5th percentiles of the chosen model's backtest errors at each horizon.
  With about 45–56 scored forecasts per horizon, the 95% band is approximate. The same backtest chose the model
  and set the ranges, which makes them slightly optimistic.
- **The 70% scenario** is a straight-line extension, not a forecast. Policy (new renewables auctions, coal plant
  retirements, private solar) can bend the curve either way.
- Code: `src/grid_pulse/forecast.py`, pure numpy, with tests in `tests/test_forecast.py`.
""")
