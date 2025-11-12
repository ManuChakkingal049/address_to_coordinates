import streamlit as st
import pandas as pd
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
from typing import Optional

# -------------------------
# Page config
# -------------------------
st.set_page_config(page_title="Address → Coordinates", page_icon="📍", layout="wide")

# -------------------------
# Helper: Geocoder (cached)
# -------------------------
@st.cache_data(show_spinner=False)
def get_geolocator():
    return Nominatim(user_agent="streamlit_address_geocoder_v1")

# Cache geocode results to avoid repeated requests during reruns
@st.cache_data(show_spinner=False)
def geocode_address(address: str) -> Optional[tuple]:
    if not address or not address.strip():
        return None
    geolocator = get_geolocator()
    geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)
    try:
        loc = geocode(address)
        if loc:
            return (loc.latitude, loc.longitude)
    except Exception:
        # Could log error if desired
        return None
    return None

# -------------------------
# Session state initialization
# -------------------------
if "results" not in st.session_state:
    st.session_state["results"] = None
if "last_input_mode" not in st.session_state:
    st.session_state["last_input_mode"] = None

# -------------------------
# UI
# -------------------------
st.title("📍 Address → Latitude & Longitude (with Map)")
st.markdown(
    "Convert a single address or multiple addresses (paste or CSV). Results are shown on an interactive map and can be downloaded."
)

col1, col2 = st.columns([1, 1])

with col1:
    mode = st.radio("Input mode", ["Single Address", "Multiple Addresses"], horizontal=True)

# Single address form
if mode == "Single Address":
    with st.form(key="single_form"):
        address = st.text_input("Enter address", placeholder="1600 Amphitheatre Parkway, Mountain View, CA")
        submit_single = st.form_submit_button("Convert")
    if submit_single:
        st.session_state["last_input_mode"] = "single"
        if not address.strip():
            st.warning("Please enter a non-empty address.")
        else:
            st.info("Looking up address — this may take a second...")
            coords = geocode_address(address)
            if coords:
                lat, lon = coords
                df = pd.DataFrame([{"address": address, "latitude": lat, "longitude": lon}])
                st.session_state["results"] = df
                st.success("Address found and saved.")
            else:
                st.error("Address not found. Try refining the address.")
# Multiple addresses form
else:
    with st.form(key="multi_form"):
        input_type = st.radio("Provide addresses by", ["Paste list (one per line)", "Upload CSV with 'address' column"], horizontal=True)
        addresses_text = ""
        uploaded_file = None
        if input_type == "Paste list (one per line)":
            addresses_text = st.text_area("Paste addresses (one per line)", height=150, placeholder="1600 Amphitheatre Pkwy, Mountain View, CA\n10 Downing St, London")
        else:
            uploaded_file = st.file_uploader("Upload CSV", type=["csv"])
        submit_multi = st.form_submit_button("Convert all")
    if submit_multi:
        st.session_state["last_input_mode"] = "multiple"
        # read addresses
        addresses = []
        if input_type.startswith("Paste"):
            if addresses_text.strip():
                addresses = [a.strip() for a in addresses_text.splitlines() if a.strip()]
            else:
                st.warning("No addresses pasted.")
        else:
            if uploaded_file is None:
                st.warning("No CSV uploaded.")
            else:
                try:
                    df_up = pd.read_csv(uploaded_file)
                    if "address" not in df_up.columns:
                        st.error("CSV must contain a column named 'address'.")
                    else:
