import streamlit as st
import pandas as pd
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
import pydeck as pdk

# -------------------------------
# App Configuration
# -------------------------------
st.set_page_config(page_title="Address → Coordinates Converter", page_icon="📍", layout="wide")

st.title("📍 Address to Coordinates & Map Visualizer")
st.markdown("""
Convert one or more addresses into **latitude & longitude**,  
and view their exact positions on an interactive map.
""")

# -------------------------------
# Geocoding Setup
# -------------------------------
geolocator = Nominatim(user_agent="geo_app_streamlit")
geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)

# -------------------------------
# User Input Mode
# -------------------------------
mode = st.radio("Select Input Type:", ["Single Address", "Multiple Addresses"], horizontal=True)

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

                # Display map
                df_map = pd.DataFrame([[lat, lon, address]], columns=["lat", "lon", "address"])
                st.pydeck_chart(pdk.Deck(
                    map_style="mapbox://styles/mapbox/streets-v12",
                    initial_view_state=pdk.ViewState(latitude=lat, longitude=lon, zoom=12, pitch=30),
                    layers=[
                        pdk.Layer(
                            "ScatterplotLayer",
                            data=df_map,
                            get_position=["lon", "lat"],
                            get_color=[255, 0, 0, 160],
                            get_radius=100,
                        ),
                        pdk.Layer(
                            "TextLayer",
                            data=df_map,
                            get_position=["lon", "lat"],
                            get_text="address",
                            get_size=14,
                            get_color=[0, 0, 0],
                            pickable=True,
                        )
                    ],
                ))
            else:
                st.error("❌ Address not found. Try refining your input.")

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
            results = []
            st.write("🔍 Converting addresses, please wait...")
            progress = st.progress(0)
            total = len(addresses)

            for i, addr in enumerate(addresses):
                loc = geocode(addr)
                if loc:
                    results.append({"address": addr, "latitude": loc.latitude, "longitude": loc.longitude})
                else:
                    results.append({"address": addr, "latitude": None, "longitude": None})
                progress.progress((i + 1) / total)

            df_result = pd.DataFrame(results)
            st.success("✅ Conversion completed!")

            st.dataframe(df_result)

            # Remove None values before plotting
            df_valid = df_result.dropna(subset=["latitude", "longitude"])

            if not df_valid.empty:
                st.subheader("🗺️ Map Visualization")
                st.pydeck_chart(pdk.Deck(
                    map_style="mapbox://styles/mapbox/streets-v12",
                    initial_view_state=pdk.ViewState(
                        latitude=df_valid["latitude"].mean(),
                        longitude=df_valid["longitude"].mean(),
                        zoom=3,
                        pitch=30,
                    ),
                    layers=[
                        pdk.Layer(
                            "ScatterplotLayer",
                            data=df_valid,
                            get_position=["longitude", "latitude"],
                            get_color=[0, 128, 255, 180],
                            get_radius=200,
                        ),
                        pdk.Layer(
                            "TextLayer",
                            data=df_valid,
                            get_position=["longitude", "latitude"],
                            get_text="address",
                            get_size=12,
                            get_color=[0, 0, 0],
                            pickable=True,
                        )
                    ],
                ))
            else:
                st.warning("No valid locations found for map display.")

            # Download option
            csv = df_result.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📥 Download results as CSV",
                data=csv,
                file_name="address_coordinates.csv",
                mime="text/csv",
            )
