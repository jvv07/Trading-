import streamlit as st

st.set_page_config(
    page_title="Trading Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

from lib.auth import require_auth

require_auth()

st.title("Trading Dashboard")
st.write("Use the sidebar to navigate.")
