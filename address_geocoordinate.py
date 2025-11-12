import streamlit as st
import pandas as pd
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
import folium
from streamlit_folium import st_folium

# ---------------------------------------------------
# Streamlit Configuration
# ---------------------------------------------------
st.set_page_config(page_title="📍 Address to Coordinates & Map", page_icon="🌍", layout="wide")
st.title("📍 Address to Coordinates & Map Visualizer")
st.markdown("""
Easily convert one or more addresses into **latitude & longitude**  
and view them on an interactive **map**.
""")

# ---------------------------------------------------
# Setup Geocoder
# ---------------------------------------------------
geolocator = Nominatim(user_agent="geo_app_streamlit")
geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)

# ---------------------------------------------------
# Input Mode
# ---------------------------------------------------
mode = st.radio("Select Input Type:", ["Single Address", "Multiple Addresses"], horizontal=True)

# ---------------------------------------------------
# Single Address Mode
# ---------------------------------------------------
if mode == "Single Address":
    address = st.text_input("Enter an address:")
    if st.button("Convert"):
        if not address.strip():
            st.warning("⚠️ Please enter a valid address.")
        else:
            location = geocode(address)
            if location:
                lat, lon = location.latitude, location.longitude
                st.success(f"✅ Found coordinates for **{address}**:")
                st.write(f"**Latitude:** {lat}")
                st.write(f"**Longitude:** {lon}")

                # Create Folium Map
                m = folium.Map(location=[lat, lon], zoom_start=13, tiles="OpenStreetMap")
                folium.Marker(
                    [lat, lon],
                    popup=address,
                    tooltip="Click for address",
                    icon=folium.Icon(color="blue", icon="info-sign")
                ).add_to(m)

                st_folium(m, width=800, height=500)
            else:
                st.error("❌ Address not found. Try refining your input.")

# ---------------------------------------------------
# Multiple Addresses Mode
# ---------------------------------------------------
else:
    st.write("You can either paste a list of addresses or upload a CSV file with an **'address'** column.")
    input_type = st.radio("Choose input method:", ["Paste List", "Upload CSV"], horizontal=True)
    addresses = []

    if input_type == "Paste List":
        addresses_text = st.text_area("Enter one address per line:")
        if addresses_text.strip():
            addresses = [a.strip() for a in addresses_text.split("\n") if a.strip()]

    elif input_type == "Upload CSV":
        uploaded_file = st.file_uploader("Upload CSV file", type=["csv"])
        if uploaded_file is not None:
            df = pd.read_csv(uploaded_file)
            if "address" not in df.columns:
                st.error("❌ CSV must contain a column named 'address'.")
            else:
                addresses = df["address"].dropna().tolist()
                st.info(f"✅ Loaded {len(addresses)} addresses.")

    if st.button("Convert All"):
        if not addresses:
            st.warning("⚠️ Please provide some addresses first.")
        else:
            st.write("🔍 Converting addresses, please wait...")
            results = []
            progress = st.progress(0)
            total = len(addresses)

            for i, addr in enumerate(addresses):
                loc = geocode(addr)
                if loc:
                    results.append({
                        "address": addr,
                        "latitude": loc.latitude,
                        "longitude": loc.longitude
                    })
                else:
                    results.append({
                        "address": addr,
                        "latitude": None,
                        "longitude": None
                    })
                progress.progress((i + 1) / total)

            df_result = pd.DataFrame(results)
            st.success("✅ Conversion completed!")
            st.dataframe(df_result)

            # Filter valid results
            df_valid = df_result.dropna(subset=["latitude", "longitude"])

            # Create and display map
            if not df_valid.empty:
                st.subheader("🗺️ Map Visualization")

                m = folium.Map(
                    location=[df_valid["latitude"].mean(), df_valid["longitude"].mean()],
                    zoom_start=4,
                    tiles="OpenStreetMap"
                )

                for _, row in df_valid.iterrows():
                    folium.Marker(
                        [row["latitude"], row["longitude"]],
                        popup=row["address"],
                        tooltip=row["address"],
                        icon=folium.Icon(color="blue", icon="info-sign")
                    ).add_to(m)

                st_folium(m, width=900, height=550)
            else:
                st.warning("No valid coordinates found to display on the map.")

            # Allow download of CSV results
            csv = df_result.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📥 Download results as CSV",
                data=csv,
                file_name="address_coordinates.csv",
                mime="text/csv"
            )
