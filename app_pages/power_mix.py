"""Page: South Africa's power mix, month by month (Ember monthly data)."""

import altair as alt
import streamlit as st

from grid_pulse.dash import query, require_data, show, style, theme
from grid_pulse.replay import replay_html

T = theme()
require_data()

# --- Filters -----------------------------------------------------------------
bounds = query("SELECT min(year(month)) AS lo, max(year(month)) AS hi, max(month) AS latest FROM marts.fct_power_mix_monthly")[0]

st.title("⚡ South Africa's power mix")
st.caption(f"Ember monthly electricity data · latest month {bounds['latest']:%B %Y}")

start, end = st.slider("Years", bounds["lo"], bounds["hi"], (bounds["lo"], bounds["hi"]))
if start == end:
    st.info("Pick at least two years to compare.")
    st.stop()

# --- KPIs: last selected year vs first -----------------------------------------
annual = query(
    """
    SELECT year(month) AS year,
           count(*) AS months,
           sum(generation_twh) AS generation_twh,
           -sum(net_imports_twh) AS net_exports_twh,
           100 * sum(coal_twh) / sum(generation_twh) AS coal_share_pct,
           100 * sum(wind_solar_twh) / sum(generation_twh) AS wind_solar_share_pct
    FROM marts.fct_power_mix_monthly
    WHERE year(month) BETWEEN ? AND ?
    GROUP BY year ORDER BY year
    """,
    (start, end),
)
first, last = annual[0], annual[-1]
partial = " (partial year)" if last["months"] < 12 else ""

k1, k2, k3 = st.columns(3)
k1.metric(f"Coal share, {last['year']}{partial}", f"{last['coal_share_pct']:.1f}%",
          f"{last['coal_share_pct'] - first['coal_share_pct']:+.1f} pts vs {first['year']}", delta_color="inverse")
k2.metric(f"Wind + solar share, {last['year']}{partial}", f"{last['wind_solar_share_pct']:.1f}%",
          f"{last['wind_solar_share_pct'] - first['wind_solar_share_pct']:+.1f} pts vs {first['year']}")
k3.metric(f"Domestic generation, {last['year']}{partial}", f"{last['generation_twh']:.0f} TWh",
          help="Excludes net imports. A partial year is not comparable with full years.")

# --- Replay: the mix month by month ------------------------------------------
GROUPS = ["Coal", "Wind & solar", "Other"]
mix = query(
    """
    SELECT strftime(month, '%Y-%m-%d') AS month,
           dense_rank() OVER (ORDER BY month) - 1 AS i,
           CASE WHEN fuel = 'Coal' THEN 'Coal'
                WHEN fuel IN ('Wind', 'Solar') THEN 'Wind & solar'
                ELSE 'Other' END AS grp,
           sum(generation_twh) AS twh
    FROM staging.stg_generation_monthly
    WHERE fuel_group <> 'Imports' AND year(month) BETWEEN ? AND ?
    GROUP BY month, grp
    ORDER BY month
    """,
    (start, end),
)
frames = [
    {"label": f"{r['month']:%b %Y}",
     "stats": {"Coal share": f"{r['coal_share_pct']:.1f}%", "Wind + solar": f"{r['wind_solar_share_pct']:.1f}%",
               "Generation": f"{r['generation_twh']:.1f} TWh"}}
    for r in query(
        """
        SELECT month, coal_share_pct, wind_solar_share_pct, generation_twh
        FROM marts.fct_power_mix_monthly WHERE year(month) BETWEEN ? AND ? ORDER BY month
        """,
        (start, end),
    )
]
y_max = max(sum(r["twh"] for r in mix if r["month"] == m) for m in {r["month"] for r in mix})

t = alt.param(name="t", value=len(frames) - 1)
replay = alt.Chart(alt.Data(values=mix)).mark_area(stroke=T["bg"], strokeWidth=1).encode(
    x=alt.X("month:T", title=None, scale=alt.Scale(domain=[mix[0]["month"], mix[-1]["month"]]),
            axis=alt.Axis(format="%Y", tickCount="year")),
    y=alt.Y("twh:Q", stack=True, title="TWh per month", scale=alt.Scale(domain=[0, y_max * 1.05])),
    color=alt.Color("grp:N", title=None, scale=alt.Scale(domain=GROUPS, range=T["series"]),
                    legend=alt.Legend(orient="top", direction="horizontal")),
    order=alt.Order("grp_order:Q"),
    tooltip=[alt.Tooltip("month:T", title="Month", format="%b %Y"), alt.Tooltip("grp:N", title="Source"),
             alt.Tooltip("twh:Q", title="TWh", format=".2f")],
).transform_calculate(
    grp_order=f"indexof({GROUPS}, datum.grp)"
).transform_filter("datum.i <= t").add_params(t)

st.subheader("Replay: generation month by month")
st.iframe(replay_html(style(replay, 300).to_dict(), frames, T), height=450)
st.caption("Press play to watch the mix evolve. Drag the slider to scrub. "
           "Other = nuclear, hydro, gas, other renewables and other fossil.")

# --- Charts ------------------------------------------------------------------
monthly = query(
    """
    SELECT strftime(month, '%Y-%m-%d') AS month,
           coal_share_pct,
           avg(coal_share_pct) OVER (ORDER BY month ROWS 11 PRECEDING) AS coal_share_12m
    FROM marts.fct_power_mix_monthly
    WHERE year(month) BETWEEN ? AND ?
    ORDER BY month
    """,
    (start, end),
)
by_fuel_month = query(
    """
    SELECT strftime(month, '%Y-%m-%d') AS month, fuel, generation_twh
    FROM staging.stg_generation_monthly
    WHERE fuel IN ('Wind', 'Solar') AND year(month) BETWEEN ? AND ?
    """,
    (start, end),
)
by_fuel = query(
    """
    SELECT fuel, sum(generation_twh) AS generation_twh
    FROM staging.stg_generation_monthly
    WHERE fuel_group <> 'Imports' AND year(month) BETWEEN ? AND ?
    GROUP BY fuel ORDER BY generation_twh DESC
    """,
    (start, end),
)

left, right = st.columns(2)

with left:
    st.subheader("Coal's share of generation")
    base = alt.Chart(alt.Data(values=monthly)).encode(x=alt.X("month:T", title=None))
    hover = alt.selection_point(fields=["month"], nearest=True, on="pointerover", empty=False)
    raw = base.mark_line(strokeWidth=1, color=T["muted"]).encode(
        y=alt.Y("coal_share_pct:Q", title="% of generation", scale=alt.Scale(zero=False)))
    smooth = base.mark_line(strokeWidth=2, color=T["series"][0]).encode(y="coal_share_12m:Q")
    rule = base.mark_rule(color=T["muted"]).encode(
        opacity=alt.condition(hover, alt.value(1), alt.value(0)),
        tooltip=[alt.Tooltip("month:T", title="Month", format="%b %Y"),
                 alt.Tooltip("coal_share_pct:Q", title="Coal share", format=".1f"),
                 alt.Tooltip("coal_share_12m:Q", title="12-month average", format=".1f")],
    ).add_params(hover)
    show(raw + smooth + rule, 320, "coal-share")
    st.caption("Grey: monthly · Blue: 12-month rolling average")

with right:
    st.subheader("Wind and solar output")
    ws = alt.Chart(alt.Data(values=by_fuel_month)).mark_bar(stroke=T["bg"], strokeWidth=1).encode(
        x=alt.X("year(month):O", title=None),
        y=alt.Y("sum(generation_twh):Q", title="TWh"),
        color=alt.Color("fuel:N", title=None, sort=["Wind", "Solar"],
                        scale=alt.Scale(domain=["Wind", "Solar"], range=T["series"][:2]),
                        legend=alt.Legend(orient="top-left")),
        order=alt.Order("fuel:N", sort="descending"),
        tooltip=[alt.Tooltip("year(month):O", title="Year"), alt.Tooltip("fuel:N", title="Source"),
                 alt.Tooltip("sum(generation_twh):Q", title="TWh", format=".1f")],
    )
    show(ws, 320, "wind-solar")
    if last["months"] < 12:
        st.caption(f"{last['year']} covers {last['months']} months so far.")

st.subheader(f"Generation by source, {start}–{end}")
total = sum(r["generation_twh"] for r in by_fuel)
for r in by_fuel:
    r["share_pct"] = 100 * r["generation_twh"] / total
bars = alt.Chart(alt.Data(values=by_fuel)).encode(
    y=alt.Y("fuel:N", sort="-x", title=None),
    x=alt.X("generation_twh:Q", title="TWh"),
)
fuel_chart = bars.mark_bar(color=T["series"][0], cornerRadiusEnd=4).encode(
    tooltip=[alt.Tooltip("fuel:N", title="Source"), alt.Tooltip("generation_twh:Q", title="TWh", format=",.1f"),
             alt.Tooltip("share_pct:Q", title="Share %", format=".1f")])
labels = bars.mark_text(align="left", dx=4, color=T["text"]).encode(text=alt.Text("share_pct:Q", format=".1f"))
show(fuel_chart + labels, 300, "by-fuel")
st.caption("Labels show % of domestic generation.")

with st.expander("Data table"):
    lines = ["| Year | Months | Generation (TWh) | Coal % | Wind + solar % | Net exports (TWh) |",
             "|---|---:|---:|---:|---:|---:|"]
    lines += [f"| {r['year']} | {r['months']} | {r['generation_twh']:.1f} | {r['coal_share_pct']:.1f} | "
              f"{r['wind_solar_share_pct']:.1f} | {r['net_exports_twh']:.1f} |" for r in annual]
    st.markdown("\n".join(lines))
