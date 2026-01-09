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
st.set_page_config(page_title="Address → Coordinates (OSM)", layout="wide")
st.title("📍 Address to Coordinates (OpenStreetMap)")

st.markdown("""
Convert single or multiple addresses into latitude & longitude using **Photon**  
with **Nominatim fallback**.  
✔ No API key required  
✔ Robust for UAE & international addresses
""")

# -----------------------------
# Constants
# -----------------------------
HEADERS = {
    "User-Agent": "streamlit-geocoder/1.0 (contact: example@email.com)"
}

# -----------------------------
# Helper functions
# -----------------------------
def clean_address(addr: str) -> str:
    """Normalize address formatting."""
    addr = re.sub(r"\s*-\s*", ", ", addr.strip())
    addr = re.sub(r"\s+", " ", addr)
    return addr.strip(", ").strip()


def geocode_photon(addr: str):
    """Photon geocoder"""
    url = "https://photon.komoot.io/api/"
    params = {"q": addr, "limit": 1}
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=10)
        r.raise_for_status()
        data = r.json()
        if data.get("features"):
            lon, lat = data["features"][0]["geometry"]["coordinates"]
            return lat, lon
    except Exception as e:
        st.warning(f"Photon failed for '{addr}': {e}")
    return None, None


def geocode_nominatim(addr: str):
    """Nominatim fallback"""
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": addr,
        "format": "json",
        "limit": 1
    }
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=10)
        r.raise_for_status()
        data = r.json()
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception as e:
        st.warning(f"Nominatim failed for '{addr}': {e}")
    return None, None


def geocode_with_fallback(addr: str):
    """Multi-step geocoding strategy"""
    addr_clean = clean_address(addr)

    # 1️⃣ Photon full address
    lat, lon = geocode_photon(addr_clean)
    if lat:
        return lat, lon, "photon_full", "Matched full address (Photon)"

    # 2️⃣ Photon city-level fallback
    parts = [p.strip() for p in addr_clean.split(",") if p.strip()]
    if len(parts) >= 2:
        fallback_addr = ", ".join(parts[-2:])
        lat, lon = geocode_photon(fallback_addr)
        if lat:
            return lat, lon, "photon_city", f"Matched fallback '{fallback_addr}'"

    # 3️⃣ Nominatim final fallback
    lat, lon = geocode_nominatim(addr_clean)
    if lat:
        return lat, lon, "nominatim", "Matched using Nominatim"

    return None, None, "not found", "No match found"


# -----------------------------
# Session state
# -----------------------------
if "results" not in st.session_state:
    st.session_state["results"] = None

# -----------------------------
# Input mode
# -----------------------------
mode = st.radio(
    "Input mode",
    ["Single Address", "Multiple Addresses"],
    horizontal=True
)

# -----------------------------
# Single Address
# -----------------------------
if mode == "Single Address":
    with st.form("single_form"):
        address = st.text_input(
            "Enter address",
            placeholder="Al Masraf Tower, Abu Dhabi"
        )
        submit = st.form_submit_button("Convert")

    if submit:
        if not address.strip():
            st.warning("Please enter a valid address.")
        else:
            st.info("Geocoding...")
            lat, lon, match_type, comment = geocode_with_fallback(address)
            st.session_state["results"] = pd.DataFrame([{
                "address": address,
                "latitude": lat,
                "longitude": lon,
                "match_type": match_type,
                "comment": comment
            }])
            st.success("Done!")

# -----------------------------
# Multiple Addresses
# -----------------------------
else:
    with st.form("multi_form"):
        input_type = st.radio(
            "Input method",
            ["Paste list (one per line)", "Upload CSV with 'address' column"],
            horizontal=True
        )

        addresses_text = ""
        uploaded_file = None

        if input_type.startswith("Paste"):
            addresses_text = st.text_area(
                "Enter one address per line",
                height=150
            )
        else:
            uploaded_file = st.file_uploader(
                "Upload CSV",
                type=["csv"]
            )

        submit = st.form_submit_button("Convert All")

    if submit:
        addresses = []

        if input_type.startswith("Paste"):
            addresses = [a.strip() for a in addresses_text.splitlines() if a.strip()]
        else:
            if uploaded_file:
                df_up = pd.read_csv(uploaded_file)
                if "address" not in df_up.columns:
                    st.error("CSV must contain 'address' column.")
                else:
                    addresses = df_up["address"].dropna().astype(str).tolist()

        if addresses:
            st.info(f"Geocoding {len(addresses)} addresses...")
            results = []
            progress = st.progress(0)

            for i, addr in enumerate(addresses):
                lat, lon, match_type, comment = geocode_with_fallback(addr)
                results.append({
                    "address": addr,
                    "latitude": lat,
                    "longitude": lon,
                    "match_type": match_type,
                    "comment": comment
                })
                progress.progress((i + 1) / len(addresses))

            st.session_state["results"] = pd.DataFrame(results)
            st.success("Batch completed!")

# -----------------------------
# Results & Map
# -----------------------------
if st.session_state["results"] is not None:
    df = st.session_state["results"]

    st.divider()
    st.subheader("Results")
    st.dataframe(df)

    # Download
    st.download_button(
        "📥 Download CSV",
        df.to_csv(index=False).encode("utf-8"),
        "address_coordinates.csv",
        "text/csv"
    )

    df_valid = df.dropna(subset=["latitude", "longitude"])

    if not df_valid.empty:
        st.subheader("Map")
        center_lat = df_valid["latitude"].mean()
        center_lon = df_valid["longitude"].mean()

        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=5,
            tiles="OpenStreetMap"
        )

        cluster = MarkerCluster().add_to(m)

        for _, row in df_valid.iterrows():
            folium.Marker(
                [row["latitude"], row["longitude"]],
                tooltip=row["address"],
                popup=f"""
                <b>{row['address']}</b><br>
                Match: {row['match_type']}<br>
                {row['comment']}
                """,
                icon=folium.Icon(color="blue")
            ).add_to(cluster)

        st_folium(m, width=900, height=550)
    else:
        st.warning("No valid coordinates to display.")
else:
    st.info("Enter an address to begin.")
