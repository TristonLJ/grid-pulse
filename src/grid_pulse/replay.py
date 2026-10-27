"""Animated "replay" chart: plays a Vega-Lite chart forward one frame at a time.

The chart spec must declare a param named `t` and filter its data on `datum.i <= t`.
Playback runs entirely in the browser (setting the `t` signal), so it's smooth and
doesn't trigger Streamlit reruns.
"""

import json

import altair as alt


def replay_html(spec: dict, frames: list[dict], colors: dict, interval_ms: int = 110) -> str:
    """frames: one dict per step i, with `label` and any `stats` shown in the counters."""
    stat_names = list(frames[0]["stats"]) if frames else []
    stat_html = "".join(
        f'<span class="stat"><span class="k">{name}</span><b data-stat="{name}"></b></span>' for name in stat_names
    )
    return f"""<!doctype html>
<html><head><meta charset="utf-8">
<script src="https://cdn.jsdelivr.net/npm/vega@{alt.VEGA_VERSION}"></script>
<script src="https://cdn.jsdelivr.net/npm/vega-lite@{alt.VEGALITE_VERSION}"></script>
<script src="https://cdn.jsdelivr.net/npm/vega-embed@{alt.VEGAEMBED_VERSION}"></script>
<style>
  html, body {{ overflow: hidden; }}
  body {{ margin: 0; background: {colors['bg']}; color: {colors['text']};
         font-family: "Source Sans Pro", system-ui, sans-serif; }}
  .hud {{ display: flex; align-items: center; gap: 20px; flex-wrap: wrap; padding: 4px 2px 10px; }}
  button {{ background: {colors['series'][0]}; color: #fff; border: 0; border-radius: 6px;
           padding: 6px 14px; font-size: 14px; cursor: pointer; min-width: 84px; }}
  button:focus-visible, input:focus-visible {{ outline: 2px solid {colors['text']}; outline-offset: 2px; }}
  .month {{ font-size: 22px; font-weight: 700; min-width: 110px; font-variant-numeric: tabular-nums; }}
  .stat {{ display: flex; flex-direction: column; font-variant-numeric: tabular-nums; }}
  .stat .k {{ font-size: 12px; color: {colors['muted']}; }}
  .stat b {{ font-size: 18px; }}
  input[type=range] {{ flex: 1; min-width: 160px; accent-color: {colors['series'][0]}; }}
</style></head>
<body>
  <div class="hud">
    <button id="play" aria-label="Play or pause the replay">▶ Play</button>
    <span class="month" id="label" aria-live="polite"></span>
    {stat_html}
    <input type="range" id="scrub" min="0" max="{len(frames) - 1}" value="{len(frames) - 1}" aria-label="Replay position">
  </div>
  <div id="vis" style="width:100%"></div>
<script>
const spec = {json.dumps(spec)};
const frames = {json.dumps(frames)};
const last = frames.length - 1;
const playBtn = document.getElementById("play"), scrub = document.getElementById("scrub");
let view, t = last, timer = null;

function render(i) {{
  t = i; scrub.value = i;
  document.getElementById("label").textContent = frames[i].label;
  for (const [k, v] of Object.entries(frames[i].stats))
    document.querySelector(`[data-stat="${{k}}"]`).textContent = v;
  if (view) view.signal("t", i).runAsync();
}}
function stop() {{ clearInterval(timer); timer = null; playBtn.textContent = "▶ Play"; }}
function play() {{
  if (t >= last) render(0);
  playBtn.textContent = "❚❚ Pause";
  timer = setInterval(() => (t >= last ? stop() : render(t + 1)), {interval_ms});
}}
playBtn.onclick = () => (timer ? stop() : play());
scrub.oninput = () => {{ stop(); render(+scrub.value); }};

vegaEmbed("#vis", spec, {{ actions: false }}).then(res => {{
  view = res.view;
  render(last);
  // Autoplay once on load, unless the viewer has asked for reduced motion
  if (!matchMedia("(prefers-reduced-motion: reduce)").matches) play();
}});
</script></body></html>"""
