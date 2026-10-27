"""grid-pulse dashboard: South Africa's electricity grid, from Ember data.

Run:  streamlit run streamlit_app.py
(Build the data first: python -m grid_pulse.ingest && python -m grid_pulse.transform)
"""

import streamlit as st

st.set_page_config(page_title="grid-pulse", page_icon="⚡", layout="wide")

st.navigation([
    st.Page("app_pages/power_mix.py", title="Power mix", icon="⚡", default=True),
    st.Page("app_pages/world.py", title="SA vs. the world", icon="🌍"),
]).run()
