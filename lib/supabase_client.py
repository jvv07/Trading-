import os
import streamlit as st
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

# Single fixed owner ID — used in all DB writes since there is no auth.
SOLO_USER_ID = "00000000-0000-0000-0000-000000000001"


@st.cache_resource
def get_client() -> Client:
    url = os.environ.get("SUPABASE_URL") or st.secrets.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_KEY") or st.secrets.get("SUPABASE_SERVICE_KEY", "")
    if not url or not key:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_SERVICE_KEY")
    return create_client(url, key)
