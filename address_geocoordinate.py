import streamlit as st
import pandas as pd
import requests
import re
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium

# -----------------------------
# Page setup
# -----------------------------
st.set_page_config(page_title="Address → Coordinates (Photon)", layout="wide")
st.title("📍 Address to Coordinates using Photon (OpenStreetMap)")

st.markdown("""
Convert single or multiple addresses into latitude & longitude using the **Photon geocoder** (based on OpenStreetMap).  
Fallback logic: full address → street + city. No API key required.
""")

# -----------------------------
# Helper functions
# -----------------------------
def clean_address(addr: str) -> str:
    """Replace dashes with commas, remove extra spaces."""
    addr_clean = re.sub(r"\s*-\s*", ", ", addr.strip())
    addr_clean = re.sub(r"\s+", " ", addr_clean)
    return addr_clean.strip(", ").strip()

def geocode_photon(addr: str):
    """Query Photon API and return (lat, lon) or (None, None)"""
    url = "https://photon.komoot.io/api/"
    params = {"q": addr, "limit": 1}
    try:
        resp = requests.get(url, params=params, timeout=5)
        data = resp.json()
        if data.get("features"):
            coords = data["features"][0]["geometry"]["coordinates"]
            return coords[1], coords[0]  # Return (lat, lon)
    except Exception:
        return None, None
    return None, None

def geocode_with_fallback(addr: str):
    """Try full address first, then street+city fallback."""
    addr_clean = clean_address(addr)
    # 1. Full address
    lat, lon = geocode_photon(addr_clean)
    if lat is not None and lon is not None:
        return lat, lon, "full", "matched full address"
    # 2. Street+city fallback
    parts = [p.strip() for p in addr_clean.split(",") if p.strip()]
    if len(parts) >= 2:
        fallback_addr = ", ".join(parts[1:])
        lat2, lon2 = geocode_photon(fallback_addr)
        if lat2 is not None and lon2 is not None:
            return lat2, lon2, "street+city", f"matched using fallback: '{fallback_addr}'"
    # Not found
    return None, None, "not found", "no match found"

# -----------------------------
# Session state
# -----------------------------
if "results" not in st.session_state:
    st.session_state["results"] = None

# -----------------------------
# Input mode
# -----------------------------
mode = st.radio("Input mode", ["Single Address", "Multiple Addresses"], horizontal=True)

# -----------------------------
# Single Address
# -----------------------------
if mode == "Single Address":
    with st.form("single_form"):
        address = st.text_input("Enter an address:", placeholder="Al Masraf Tower - Hamdan Bin Mohammed St - Al Zahiyah - Abu Dhabi")
        submit = st.form_submit_button("Convert")
    if submit:
        if not address.strip():
            st.warning("Please enter a valid address.")
        else:
            st.info("Geocoding...")
            lat, lon, match_type, comment = geocode_with_fallback(address)
            df = pd.DataFrame([{
                "address": address,
                "latitude": lat,
                "longitude": lon,
                "match_type": match_type,
                "comment": comment
            }])
            st.session_state["results"] = df
            st.success("Done!")

# -----------------------------
# Multiple Addresses
# -----------------------------
else:
    with st.form("multi_form"):
        input_type = st.radio("Input method:", ["Paste list (one per line)", "Upload CSV with 'address' column"], horizontal=True)
        addresses_text = ""
        uploaded_file = None
        if input_type.startswith("Paste"):
            addresses_text = st.text_area("Enter one address per line:", height=150)
        else:
            uploaded_file = st.file_uploader("Upload CSV", type=["csv"])
        submit = st.form_submit_button("Convert All")
    if submit:
        addresses = []
        if input_type.startswith("Paste"):
            if addresses_text.strip():
                addresses = [a.strip() for a in addresses_text.splitlines() if a.strip()]
        else:
            if uploaded_file is not None:
                try:
                    df_up = pd.read_csv(uploaded_file)
                    if "address" not in df_up.columns:
                        st.error("CSV must contain a column named 'address'.")
                    else:
                        addresses = df_up["address"].dropna().astype(str).tolist()
                        st.write(f"✅ Loaded {len(addresses)} addresses.")
                except Exception as e:
                    st.error(f"Error reading CSV: {e}")

        if addresses:
            st.info(f"Geocoding {len(addresses)} addresses...")
            results = []
            progress = st.progress(0)
            total = len(addresses)
            for i, addr in enumerate(addresses):
                lat, lon, match_type, comment = geocode_with_fallback(addr)
                results.append({
                    "address": addr,
                    "latitude": lat,
                    "longitude": lon,
                    "match_type": match_type,
                    "comment": comment
                })
                progress.progress((i+1)/total)
            df_result = pd.DataFrame(results)
            st.session_state["results"] = df_result
            st.success("Batch finished.")

# -----------------------------
# Display results & map
# -----------------------------
if st.session_state["results"] is not None:
    df_result = st.session_state["results"]

    # Ensure numeric lat/lon
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
            if pd.notna(row["latitude"]) and pd.notna(row["longitude"]):
                color = "blue" if row["match_type"] != "not found" else "red"
                popup_html = folium.Popup(
                    f"{row['address']}<br>Match type: {row['match_type']}<br>Comment: {row['comment']}",
                    max_width=400, parse_html=True
                )
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
