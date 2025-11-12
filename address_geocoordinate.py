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
                        addresses = df_up["address"].dropna().astype(str).tolist()
                        st.info(f"Loaded {len(addresses)} addresses from CSV.")
                except Exception as e:
                    st.error(f"Error reading CSV: {e}")

        # If we have addresses, geocode them
        if addresses:
            st.info(f"Converting {len(addresses)} addresses — this may take a while depending on count.")
            results = []
            progress = st.progress(0)
            total = len(addresses)
            for i, addr in enumerate(addresses):
                coords = geocode_address(addr)
                if coords:
                    lat, lon = coords
                    results.append({"address": addr, "latitude": lat, "longitude": lon})
                else:
                    results.append({"address": addr, "latitude": None, "longitude": None})
                progress.progress((i + 1) / total)
            st.session_state["results"] = pd.DataFrame(results)
            st.success("Batch geocoding finished.")

# -------------------------
# Display results and map (if available)
# -------------------------
if st.session_state["results"] is not None:
    df_result = st.session_state["results"]
    st.divider()
    st.subheader("Results")
    st.dataframe(df_result)

    # Download button
    csv_bytes = df_result.to_csv(index=False).encode("utf-8")
    st.download_button("📥 Download CSV", data=csv_bytes, file_name="address_coordinates.csv", mime="text/csv")

    # Map visualization for valid coords
    df_valid = df_result.dropna(subset=["latitude", "longitude"])
    if not df_valid.empty:
        st.subheader("Map")
        # center map on mean coordinate
        center_lat = float(df_valid["latitude"].mean())
        center_lon = float(df_valid["longitude"].mean())
        m = folium.Map(location=[center_lat, center_lon], zoom_start=4, tiles="OpenStreetMap")

        # Marker cluster
        marker_cluster = MarkerCluster().add_to(m)

        for _, row in df_valid.iterrows():
            popup_html = folium.Popup(row["address"], parse_html=True, max_width=450)
            folium.Marker(
                [row["latitude"], row["longitude"]],
                popup=popup_html,
                tooltip=row["address"],
                icon=folium.Icon(color="blue", icon="info-sign")
            ).add_to(marker_cluster)

        # Display with streamlit_folium (this persists across reruns because st.session_state stores df)
        st_folium(m, width=900, height=550)
    else:
        st.warning("No valid coordinates to show on the map.")
else:
    st.info("No results yet — enter an address or upload/paste addresses and click Convert.")
