"""Page: South Africa vs. its peers and the world (Ember yearly data, 2000 onwards)."""

import altair as alt
import streamlit as st

from grid_pulse.dash import query, require_data, show, style, theme
from grid_pulse.replay import replay_html

T = theme()
require_data()

SA = "South Africa"
SUBSTEPS = 8          # interpolated frames per year, so race bars slide instead of jumping
CAR_TONNES = 4.6      # US EPA: CO2 from a typical passenger vehicle per year

peers = query("""
    SELECT entity, is_benchmark, year, wind_solar_share_pct AS share, gco2_per_kwh
    FROM marts.fct_peer_transition_yearly ORDER BY year, entity
""")
co2 = query("SELECT * FROM marts.fct_co2_avoided_yearly ORDER BY year")
years = sorted({r["year"] for r in peers})
latest = years[-1]
by = {(r["entity"], r["year"]): r for r in peers}
entities = sorted({r["entity"] for r in peers})
benchmarks = {r["entity"] for r in peers if r["is_benchmark"]}


def ranks(year: int, countries_only: bool = False) -> dict[str, int]:
    pool = [e for e in entities if not (countries_only and e in benchmarks)]
    ordered = sorted(pool, key=lambda e: by[(e, year)]["share"], reverse=True)
    return {e: i for i, e in enumerate(ordered)}


st.title("🌍 South Africa vs. the world")
st.caption(f"How fast is SA moving off coal compared with {len(entities) - len(benchmarks) - 1} peer countries? "
           f"Ember yearly data, {years[0]}–{latest}.")

# --- KPIs ----------------------------------------------------------------------
sa, world, africa = by[(SA, latest)], by[("World", latest)], by[("Africa", latest)]
country_rank = ranks(latest, countries_only=True)[SA] + 1
n_countries = len(entities) - len(benchmarks)
c = co2[-1]

k1, k2, k3, k4 = st.columns(4)
k1.metric(f"Wind + solar share, {latest}", f"{sa['share']:.1f}%",
          f"{sa['share'] - world['share']:+.1f} pts vs World", help=f"Africa: {africa['share']:.1f}%")
k2.metric("Rank among peers", f"#{country_rank} of {n_countries}", help="Countries only, by wind + solar share.")
k3.metric(f"Grid carbon intensity, {latest}", f"{sa['gco2_per_kwh']:.0f} g/kWh",
          f"{100 * (sa['gco2_per_kwh'] / world['gco2_per_kwh'] - 1):+.0f}% vs World", delta_color="inverse")
k4.metric(f"CO₂ avoided by wind + solar, {latest}",
          f"{c['avoided_low_mtco2']:.1f}–{c['avoided_high_mtco2']:.1f} Mt",
          help="Range from two assumptions about what wind and solar replaced. See Method below.")

# --- Race: wind + solar share, year by year --------------------------------------
race_rows, frames = [], []
for y0, y1 in zip(years, years[1:] + [None]):
    r0 = ranks(y0)
    r1 = ranks(y1) if y1 else r0
    for s in range(SUBSTEPS if y1 else 1):
        f = s / SUBSTEPS
        i = len(frames)
        for e in entities:
            v0 = by[(e, y0)]["share"]
            v = v0 + ((by[(e, y1)]["share"] if y1 else v0) - v0) * f
            race_rows.append({
                "i": i, "entity": e, "share": round(v, 2),
                "pos": r0[e] + (r1[e] - r0[e]) * f,
                "kind": "South Africa" if e == SA else "Benchmark" if e in benchmarks else "Peer",
                "label": f"{e}  {v:.1f}%",
            })
        shown = y1 if (y1 and f >= 0.5) else y0
        frames.append({"label": str(shown), "stats": {
            "SA rank": f"#{ranks(shown, countries_only=True)[SA] + 1} of {n_countries}",
            "SA share": f"{by[(SA, shown)]['share']:.1f}%",
            "World": f"{by[('World', shown)]['share']:.1f}%",
        }})

n = len(entities)
x_max = max(r["share"] for r in race_rows) * 1.18  # headroom for the labels
t = alt.param(name="t", value=len(frames) - 1)
race_base = alt.Chart(alt.Data(values=race_rows)).transform_filter("datum.i == t").encode(
    y=alt.Y("pos:Q", axis=None, scale=alt.Scale(domain=[-0.6, n - 0.4], reverse=True)),
    # stack=None: mid-swap two bars share a position, and Vega would otherwise add them end to end
    x=alt.X("share:Q", title="Wind + solar share of domestic generation (%)", stack=None,
            scale=alt.Scale(domain=[0, x_max])),
)
# Both axes are quantitative (pos is fractional so bars can slide), so orientation must be explicit
race_bars = race_base.mark_bar(orient="horizontal", height=20, cornerRadiusEnd=4).encode(
    color=alt.Color("kind:N", title=None, scale=alt.Scale(domain=["South Africa", "Benchmark", "Peer"],
                                                        range=[T["series"][0], T["series"][1], T["muted"]]),
                    legend=alt.Legend(orient="top", direction="horizontal")),
    tooltip=[alt.Tooltip("entity:N", title="Country / region"), alt.Tooltip("share:Q", title="Share %", format=".1f")],
)
race_labels = race_base.mark_text(align="left", dx=6, color=T["text"], fontSize=12).encode(text="label:N")

st.subheader("The race to wind and solar")
st.iframe(replay_html(style((race_bars + race_labels).add_params(t), 460).to_dict(), frames, T, interval_ms=55),
          height=590)
st.caption("Benchmark = World and Africa totals. Peers were chosen for being sunny, coal-heavy or emerging "
           "economies like SA's.")

# --- Carbon intensity over time ----------------------------------------------------
left, right = st.columns(2)

with left:
    st.subheader("Grid carbon intensity")
    trio = [SA, "World", "Africa"]
    ci_rows = [{"year": r["year"], "entity": r["entity"], "g": r["gco2_per_kwh"]} for r in peers if r["entity"] in trio]
    ends = [r for r in ci_rows if r["year"] == latest]
    color = alt.Color("entity:N", title=None, scale=alt.Scale(domain=trio, range=T["series"][:3]),
                      legend=alt.Legend(orient="top", direction="horizontal"))
    lines = alt.Chart(alt.Data(values=ci_rows)).mark_line(strokeWidth=2).encode(
        x=alt.X("year:O", title=None, axis=alt.Axis(values=years[::5], labelAngle=0)),
        y=alt.Y("g:Q", title="g CO₂ per kWh", scale=alt.Scale(zero=False)),
        color=color,
        tooltip=[alt.Tooltip("entity:N"), alt.Tooltip("year:O"), alt.Tooltip("g:Q", title="g/kWh", format=".0f")],
    )
    points = alt.Chart(alt.Data(values=ci_rows)).mark_circle(size=60, opacity=0).encode(
        x="year:O", y="g:Q", tooltip=[alt.Tooltip("entity:N"), alt.Tooltip("year:O"),
                                      alt.Tooltip("g:Q", title="g/kWh", format=".0f")])
    end_labels = alt.Chart(alt.Data(values=ends)).mark_text(align="left", dx=6, color=T["text"]).encode(
        x="year:O", y="g:Q", text=alt.Text("g:Q", format=".0f"))
    show(lines + points + end_labels, 320, "intensity", pad=95)
    st.caption(f"SA's grid emits {sa['gco2_per_kwh'] / world['gco2_per_kwh']:.1f}x the world average per kWh.")

with right:
    st.subheader("CO₂ avoided by SA's wind and solar")
    co2_rows = [r for r in co2 if r["year"] >= 2010]
    base = alt.Chart(alt.Data(values=co2_rows)).encode(x=alt.X("year:O", title=None, axis=alt.Axis(labelAngle=0)))
    tips = [alt.Tooltip("year:O", title="Year"),
            alt.Tooltip("avoided_low_mtco2:Q", title="At least (Mt)", format=".1f"),
            alt.Tooltip("avoided_high_mtco2:Q", title="Up to (Mt)", format=".1f")]
    high = base.mark_bar(color=T["series"][0], opacity=0.35, cornerRadiusEnd=4).encode(
        y=alt.Y("avoided_high_mtco2:Q", title="Mt CO₂ per year"), tooltip=tips)
    low = base.mark_bar(color=T["series"][0], cornerRadiusEnd=4).encode(y="avoided_low_mtco2:Q", tooltip=tips)
    show(high + low, 320, "co2")
    st.caption("Solid: at least (replaced average grid power) · Light: up to (replaced coal power).")

lo_cars, hi_cars = (c[k] * 1e6 / CAR_TONNES / 1e6 for k in ("avoided_low_mtco2", "avoided_high_mtco2"))
st.info(
    f"**In {latest}, wind and solar kept {c['avoided_low_mtco2']:.1f}–{c['avoided_high_mtco2']:.1f} Mt of CO₂ "
    f"out of the air**, about what {lo_cars:.1f}–{hi_cars:.1f} million cars emit in a year. "
    f"Since {years[0]} the total is {c['cumulative_low_mtco2']:.0f}–{c['cumulative_high_mtco2']:.0f} Mt. "
    f"Without them, SA's grid would have run at about {c['counterfactual_gco2_per_kwh']:.0f} g/kWh "
    f"instead of {c['gco2_per_kwh']:.0f}."
)

with st.expander("Method and caveats"):
    st.markdown(f"""
- **What we estimate:** the CO₂ that would have been emitted if the electricity from wind and solar
  had come from other plants instead.
- **High estimate:** it would all have come from **coal**, at that year's average coal emission rate
  (coal CO₂ ÷ coal TWh, about {c['coal_mt_per_twh']:.2f} kg/kWh). This is a reasonable upper bound for SA, where coal
  supplies most of the power that wind and solar could displace.
- **Low estimate:** it would have come from the **average grid mix** at that year's carbon intensity.
- **Not modelled:** the fact that wind and solar output varies (backup plants may run less efficiently),
  and how Ember counts rooftop solar. Each step from one assumption to the next is shown in
  `sql/marts/fct_co2_avoided_yearly.sql`.
- **Cars comparison:** {CAR_TONNES} t CO₂ per typical passenger vehicle per year (US EPA).
""")

with st.expander(f"Data table, {latest}"):
    rk = ranks(latest)
    lines_md = ["| Rank | Country / region | Wind + solar % | g CO₂/kWh |", "|---:|---|---:|---:|"]
    lines_md += [f"| {rk[e] + 1} | {'**' + e + '**' if e == SA else e} | {by[(e, latest)]['share']:.1f} | "
                 f"{by[(e, latest)]['gco2_per_kwh']:.0f} |" for e in sorted(entities, key=rk.get)]
    st.markdown("\n".join(lines_md))
