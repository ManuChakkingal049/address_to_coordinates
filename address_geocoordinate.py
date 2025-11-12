import streamlit as st
import pandas as pd
from typing import Optional
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
import re

# -------------------------
# Page configuration
# -------------------------
st.set_page_config(page_title="Address → Coordinates (Robust)", page_icon="📍", layout="wide")
st.title("📍 Address → Coordinates (Fuzzy Matching, Arabic/Latin)")
st.markdown("""
Convert single or multiple addresses into **latitude & longitude**.  
Automatically fallback if the full address does not match, and record the match type.
""")

# -------------------------
# Session state
# -------------------------
if "results" not in st.session_state:
    st.session_state["results"] = None

# -------------------------
# Clean address
# -------------------------
def clean_address(addr: str) -> str:
    """Replace dashes with commas and remove extra spaces."""
    addr_clean = re.sub(r"\s*-\s*", ", ", addr.strip())
    addr_clean = re.sub(r"\s+", " ", addr_clean)
    return addr_clean

# -------------------------
# Geocode with fallback
# -------------------------
def geocode_fallback(addr: str, geolocator, geocode_fn) -> tuple:
    """
    Returns numeric (lat, lon) and match_type.
    If geocoding fails, returns (None, None, "not found").
    """
    addr_clean = clean_address(addr)

    # 1. Full address
    loc = geocode_fn(addr_clean)
    if loc:
        return float(loc.latitude), float(loc.longitude), "full"

    # 2. Remove first part (building name) → street + city
    parts = [p.strip() for p in addr_clean.split(",") if p.strip()]
    if len(parts) >= 2:
        addr_street_city = ", ".join(parts[1:])
        loc = geocode_fn(addr_street_city)
        if loc:
            return float(loc.latitude), float(loc.longitude), "street+city"

    # 3. Last two parts → city/province
    if len(parts) >= 1:
        addr_city = ", ".join(parts[-2:])
        loc = geocode_fn(addr_city)
        if loc:
            return float(loc.latitude), float(loc.longitude), "city"

    # 4. Not found
    return None, None, "not found"

# -------------------------
# Geopy setup
# -------------------------
geolocator = Nominatim(user_agent="streamlit_address_fuzzy")
geocode_fn = RateLimiter(geolocator.geocode, min_delay_seconds=1)

# -------------------------
# Input mode
# -------------------------
mode = st.radio("Input mode", ["Single Address", "Multiple Addresses"], horizontal=True)

# -------------------------
# Single address
# -------------------------
if mode == "Single Address":
    with st.form("single_form"):
        address = st.text_input(
            "Enter address",
            placeholder="Al Masraf Tower - Hamdan Bin Mohammed St - Al Zahiyah - E15 - Abu Dhabi"
        )
        submit_single = st.form_submit_button("Convert")
    if submit_single:
        if not address.strip():
            st.warning("Enter a valid address")
        else:
            st.info("Geocoding...")
            lat, lon, match_type = geocode_fallback(address, geolocator, geocode_fn)
            df = pd.DataFrame([{"address": address, "latitude": lat, "longitude": lon, "match_type": match_type}])
            st.session_state["results"] = df
            st.success("Done!")

# -------------------------
# Multiple addresses
# -------------------------
else:
    with st.form("multi_form"):
        input_type = st.radio(
            "Provide addresses by",
            ["Paste list (one per line)", "Upload CSV with 'address' column"],
            horizontal=True
        )
        addresses_text = ""
        uploaded_file = None
        if input_type.startswith("Paste"):
            addresses_text = st.text_area("Paste addresses (one per line)", height=150)
        else:
            uploaded_file = st.file_uploader("Upload CSV", type=["csv"])
        submit_multi = st.form_submit_button("Convert all")

    if submit_multi:
        addresses = []
        if input_type.startswith("Paste"):
            if addresses_text.strip():
                addresses = [a.strip() for a in addresses_text.splitlines() if a.strip()]
        else:
            if uploaded_file is not None:
                df_up = pd.read_csv(uploaded_file)
                if "address" in df_up.columns:
                    addresses = df_up["address"].dropna().astype(str).tolist()
                else:
                    st.error("CSV must contain 'address' column")
                    addresses = []

        if addresses:
            st.info(f"Geocoding {len(addresses)} addresses...")
            results = []
            progress = st.progress(0)
            for i, addr in enumerate(addresses):
                lat, lon, match_type = geocode_fallback(addr, geolocator, geocode_fn)
                results.append({"address": addr, "latitude": lat, "longitude": lon, "match_type": match_type})
                progress.progress((i + 1) / len(addresses))
            df_result = pd.DataFrame(results)
            st.session_state["results"] = df_result
            st.success("Done!")

# -------------------------
# Display results and map
# -------------------------
if st.session_state["results"] is not None:
    df_result = st.session_state["results"]

    # Ensure numeric latitude/longitude
    df_result["latitude"] = pd.to_numeric(df_result["latitude"], errors="coerce")
    df_result["longitude"] = pd.to_numeric(df_result["longitude"], errors="coerce")
    df_valid = df_result.dropna(subset=["latitude", "longitude"])

    st.divider()
    st.subheader("Results")
    st.dataframe(df_result)

    # Download CSV
    csv_bytes = df_result.to_csv(index=False).encode("utf-8")
    st.download_button("📥 Download CSV", data=csv_bytes, file_name="address_coordinates.csv", mime="text/csv")

    # Map
    if not df_valid.empty:
        st.subheader("Map")
        center_lat = float(df_valid["latitude"].mean())
        center_lon = float(df_valid["longitude"].mean())
        m = folium.Map(location=[center_lat, center_lon], zoom_start=5, tiles="OpenStreetMap")

        marker_cluster = MarkerCluster().add_to(m)
        for _, row in df_result.iterrows():
            # Color red if not found
            color = "blue" if row["match_type"] != "not found" else "red"
            popup_html = folium.Popup(
                f"{row['address']}<br>Match type: {row['match_type']}",
                parse_html=True
            )
            if pd.notna(row["latitude"]) and pd.notna(row["longitude"]):
                folium.Marker(
                    [row["latitude"], row["longitude"]],
                    popup=popup_html,
                    tooltip=row["address"],
                    icon=folium.Icon(color=color, icon="info-sign")
                ).add_to(marker_cluster)

        st_folium(m, width=900, height=550)
    else:
        st.warning("No valid coordinates to show on the map.")
else:
    st.info("No results yet — enter an address or upload/paste addresses and click Convert.")
