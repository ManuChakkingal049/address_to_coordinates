import streamlit as st
import pandas as pd
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

# Initialize geocoder
geolocator = Nominatim(user_agent="geo_app")
geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)

st.title("📍 Address to Latitude & Longitude Converter")

st.write("Convert single or multiple addresses into geographic coordinates (Latitude & Longitude).")

# Input mode selection
mode = st.radio("Select Input Type:", ["Single Address", "Multiple Addresses"])

if mode == "Single Address":
    address = st.text_input("Enter an address:")
    if st.button("Convert"):
        if address.strip() == "":
            st.warning("Please enter a valid address.")
        else:
            location = geocode(address)
            if location:
                st.success(f"✅ Address found!")
                st.write(f"**Latitude:** {location.latitude}")
                st.write(f"**Longitude:** {location.longitude}")
            else:
                st.error("Address not found. Try refining your input.")

else:
    st.write("You can either paste a list of addresses or upload a CSV file with an 'address' column.")
    input_type = st.radio("Choose input method:", ["Paste List", "Upload CSV"])

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
                st.error("CSV must contain a column named 'address'.")
            else:
                addresses = df["address"].dropna().tolist()
                st.write(f"✅ Loaded {len(addresses)} addresses.")

    if st.button("Convert All"):
        if not addresses:
            st.warning("Please provide addresses first.")
        else:
            results = []
            st.write("Converting addresses, please wait...")
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
            st.success("Conversion completed!")
            st.dataframe(df_result)

            csv = df_result.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📥 Download results as CSV",
                data=csv,
                file_name="address_coordinates.csv",
                mime="text/csv"
            )
