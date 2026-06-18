import json
import os
import re
import urllib.parse

import pandas as pd
import streamlit as st

try:
    import folium
    from streamlit_folium import st_folium

    HAS_FOLIUM = True
except ImportError:
    HAS_FOLIUM = False

try:
    from mistralai.client import Mistral

    HAS_MISTRAL = True
except ImportError:
    HAS_MISTRAL = False


st.set_page_config(page_title="Trip Planner AI", layout="wide")


def local_css(file_path):
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


local_css("src/style.css")

try:
    API_KEY = st.secrets.get("MISTRAL_API_KEY", "")
except Exception:
    API_KEY = ""


COUNTRIES_AND_CITIES = {
    "Pakistan": ["Lahore", "Karachi", "Islamabad", "Rawalpindi", "Peshawar", "Multan", "Faisalabad"],
    "United Kingdom": ["London", "Manchester", "Birmingham", "Edinburgh", "Glasgow", "Liverpool"],
    "France": ["Paris", "Lyon", "Marseille", "Nice", "Toulouse", "Bordeaux"],
    "Japan": ["Tokyo", "Kyoto", "Osaka", "Yokohama", "Sapporo", "Hiroshima"],
    "United States": ["New York", "Los Angeles", "Chicago", "Miami", "San Francisco", "Las Vegas"],
    "United Arab Emirates": ["Dubai", "Abu Dhabi", "Sharjah", "Ajman"],
    "Saudi Arabia": ["Riyadh", "Jeddah", "Mecca", "Medina", "Dammam"],
    "Italy": ["Rome", "Milan", "Venice", "Florence", "Naples"],
    "Other": [],
}


def demo_trip_data(destination):
    return {
        "destination": destination,
        "hotels": [
            {
                "name": "Central Comfort Hotel",
                "star_rating": 3,
                "price_estimate": "$120 per night",
                "address": f"City center, {destination}",
                "latitude": 0,
                "longitude": 0,
            },
            {
                "name": "Grand Stay Suites",
                "star_rating": 4,
                "price_estimate": "$190 per night",
                "address": f"Downtown, {destination}",
                "latitude": 0,
                "longitude": 0,
            },
            {
                "name": "Budget Traveler Inn",
                "star_rating": 2,
                "price_estimate": "$70 per night",
                "address": f"Main road, {destination}",
                "latitude": 0,
                "longitude": 0,
            },
        ],
        "food": [
            {
                "name": "Local Table",
                "cuisine": "Local cuisine",
                "price_range": "Moderate",
                "price_min_local": 15,
                "price_max_local": 35,
                "local_currency_symbol": "$",
                "address": f"Main market, {destination}",
                "latitude": 0,
                "longitude": 0,
            },
            {
                "name": "Street Bites",
                "cuisine": "Casual dining",
                "price_range": "Budget",
                "price_min_local": 5,
                "price_max_local": 15,
                "local_currency_symbol": "$",
                "address": f"Food street, {destination}",
                "latitude": 0,
                "longitude": 0,
            },
            {
                "name": "Skyline Restaurant",
                "cuisine": "International",
                "price_range": "Premium",
                "price_min_local": 35,
                "price_max_local": 80,
                "local_currency_symbol": "$",
                "address": f"Downtown, {destination}",
                "latitude": 0,
                "longitude": 0,
            },
        ],
        "attractions": [
            {
                "name": "Historic City Walk",
                "one_sentence_description": "A relaxed route through the most popular central sights.",
                "price_min_local": 0,
                "price_max_local": 20,
                "local_currency_symbol": "$",
                "address": f"Old town, {destination}",
                "latitude": 0,
                "longitude": 0,
            },
            {
                "name": "Main Museum",
                "one_sentence_description": "A good first stop for local history, culture, and indoor sightseeing.",
                "price_min_local": 10,
                "price_max_local": 25,
                "local_currency_symbol": "$",
                "address": f"Museum district, {destination}",
                "latitude": 0,
                "longitude": 0,
            },
            {
                "name": "Central Park Viewpoint",
                "one_sentence_description": "An easy outdoor stop for photos, rest, and skyline views.",
                "price_min_local": 0,
                "price_max_local": 0,
                "local_currency_symbol": "$",
                "address": f"Central park, {destination}",
                "latitude": 0,
                "longitude": 0,
            },
        ],
        "transport": {
            "ride_apps": ["Uber", "Careem"],
            "public_transit": "Use local buses, metro, taxis, and ride-hailing apps depending on availability.",
            "transit_stations": [],
        },
    }


def extract_json(text, default):
    if not text:
        return default
    match = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    cleaned = match.group(1).strip() if match else text.strip()
    starts = [pos for pos in [cleaned.find("{"), cleaned.find("[")] if pos != -1]
    if starts:
        start = min(starts)
        end = max(cleaned.rfind("}"), cleaned.rfind("]"))
        if end > start:
            cleaned = cleaned[start : end + 1]
    try:
        parsed = json.loads(cleaned)
        if isinstance(default, list) and not isinstance(parsed, list):
            return default
        if isinstance(default, dict) and not isinstance(parsed, dict):
            return default
        return parsed
    except json.JSONDecodeError:
        return default


def response_text(response):
    for entry in getattr(response, "outputs", []):
        if getattr(entry, "type", "") == "message.output":
            content = getattr(entry, "content", "")
            if isinstance(content, list):
                return "".join(getattr(chunk, "text", str(chunk)) for chunk in content)
            return str(content)
    return ""


def ask_mistral(destination, defaults):
    if not API_KEY or not HAS_MISTRAL:
        return defaults

    client = Mistral(api_key=API_KEY)
    prompts = {
        "hotels": (
            f"Find 5 real hotels in {destination}. Return only JSON array with name, "
            "star_rating, price_estimate, address, latitude, longitude."
        ),
        "food": (
            f"Find 5 real restaurants in {destination}. Return only JSON array with name, cuisine, "
            "price_range, price_min_local, price_max_local, local_currency_symbol, address, latitude, longitude."
        ),
        "attractions": (
            f"Find 5 real attractions in {destination}. Return only JSON array with name, "
            "one_sentence_description, price_min_local, price_max_local, local_currency_symbol, address, latitude, longitude."
        ),
        "transport": (
            f"Find ride hailing apps and public transit options for {destination}. Return only JSON object "
            "with ride_apps array, public_transit string, transit_stations array."
        ),
    }

    data = dict(defaults)
    for key, prompt in prompts.items():
        try:
            response = client.beta.conversations.start(
                model="mistral-large-latest",
                inputs=[{"type": "message.input", "role": "user", "content": prompt}],
            )
            data[key] = extract_json(response_text(response), defaults[key])
        except Exception as exc:
            st.warning(f"{key.title()} lookup failed, using fallback data. {exc}")
            data[key] = defaults[key]
    return data


def safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def price_number(value):
    match = re.search(r"\d[\d,]*", str(value or ""))
    return float(match.group(0).replace(",", "")) if match else 0.0


def currency_symbol(data):
    for item in data.get("food", []) + data.get("attractions", []):
        if item.get("local_currency_symbol"):
            return str(item["local_currency_symbol"])
    for hotel in data.get("hotels", []):
        estimate = str(hotel.get("price_estimate", ""))
        for symbol in ["PKR", "Rs.", "$", "GBP", "EUR", "JPY", "AED"]:
            if symbol in estimate:
                return symbol
    return "$"


def navigation_button(label, address, key):
    if address:
        url = f"https://www.google.com/maps/dir/?api=1&destination={urllib.parse.quote(address)}"
        st.link_button(label, url, key=key, use_container_width=True)


def render_trip(data, travelers, days):
    destination = data["destination"]
    st.markdown(f"### Destination: **{destination}**")
    st.write(f"**{travelers} Travelers** | **{days} Days**")

    tab_itinerary, tab_map, tab_budget = st.tabs(["Itinerary Planner", "Interactive Map", "Transit & Budgets"])

    with tab_itinerary:
        st.markdown("### Recommended Accommodations")
        hotels = data.get("hotels", [])
        if hotels:
            cols = st.columns(min(len(hotels), 3))
            for idx, hotel in enumerate(hotels):
                with cols[idx % len(cols)]:
                    st.markdown(
                        f"""
                        <div class="card-container hover-card-{idx % 5}">
                            <div class="card-title">{hotel.get('name', 'Hotel')}</div>
                            <div class="badge-group">
                                <span class="badge-pill badge-hotel">{hotel.get('star_rating', 'N/A')} Star</span>
                                <span class="badge-pill badge-hotel">{hotel.get('price_estimate', 'Price unavailable')}</span>
                            </div>
                            <div class="card-subtitle">{hotel.get('address', '')}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    navigation_button("Navigate", hotel.get("address"), f"nav_hotel_{idx}")
        else:
            st.info("No hotel results available.")

        st.markdown("---")
        st.markdown("### Daily Sightseeing & Dining")
        daily_tabs = st.tabs([f"Day {day}" for day in range(1, int(days) + 1)])
        for day in range(1, int(days) + 1):
            with daily_tabs[day - 1]:
                food = [item for idx, item in enumerate(data.get("food", [])) if (idx % int(days)) + 1 == day]
                attractions = [item for idx, item in enumerate(data.get("attractions", [])) if (idx % int(days)) + 1 == day]
                col_food, col_attr = st.columns(2)
                with col_food:
                    st.markdown("#### Culinary Highlights")
                    for idx, item in enumerate(food):
                        st.markdown(
                            f"""
                            <div class="card-container hover-card-{idx % 5}">
                                <div class="card-title">{item.get('name', 'Restaurant')}</div>
                                <div class="badge-group">
                                    <span class="badge-pill badge-food">{item.get('cuisine', 'Cuisine')}</span>
                                    <span class="badge-pill badge-food">{item.get('price_range', 'Price unavailable')}</span>
                                </div>
                                <div class="card-subtitle">{item.get('address', '')}</div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                        navigation_button("Navigate", item.get("address"), f"nav_food_{day}_{idx}")
                with col_attr:
                    st.markdown("#### Attractions & Tours")
                    for idx, item in enumerate(attractions):
                        st.markdown(
                            f"""
                            <div class="card-container hover-card-{idx % 5}">
                                <div class="card-title">{item.get('name', 'Attraction')}</div>
                                <div class="card-description">{item.get('one_sentence_description', '')}</div>
                                <div class="card-subtitle">{item.get('address', '')}</div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                        navigation_button("Navigate", item.get("address"), f"nav_attr_{day}_{idx}")

    with tab_map:
        st.subheader("Destination Map View")
        points = []
        for section in ["hotels", "food", "attractions"]:
            for item in data.get(section, []):
                lat = safe_float(item.get("latitude"))
                lon = safe_float(item.get("longitude"))
                if lat and lon:
                    points.append({"lat": lat, "lon": lon})
        if points and HAS_FOLIUM:
            avg_lat = sum(point["lat"] for point in points) / len(points)
            avg_lon = sum(point["lon"] for point in points) / len(points)
            st_folium(folium.Map(location=[avg_lat, avg_lon], zoom_start=13), width="100%", height=600)
        elif points:
            st.map(pd.DataFrame(points))
        else:
            st.info("No map coordinates returned yet. Navigation buttons still open Google Maps by address.")

    with tab_budget:
        symbol = currency_symbol(data)
        hotel_prices = [price_number(hotel.get("price_estimate")) for hotel in data.get("hotels", [])]
        hotel_prices = [price for price in hotel_prices if price > 0]
        avg_hotel = sum(hotel_prices) / len(hotel_prices) if hotel_prices else 150
        food_min = sum(safe_float(item.get("price_min_local")) for item in data.get("food", [])) or 15
        food_max = sum(safe_float(item.get("price_max_local")) for item in data.get("food", [])) or 45
        attr_min = sum(safe_float(item.get("price_min_local")) for item in data.get("attractions", []))
        attr_max = sum(safe_float(item.get("price_max_local")) for item in data.get("attractions", []))
        total = (avg_hotel * int(days)) + ((food_min + food_max) / 2 * int(travelers)) + ((attr_min + attr_max) / 2)

        col_cost, col_transport = st.columns(2)
        with col_cost:
            st.markdown("### Budget Breakdown")
            st.metric("Estimated Total Trip Cost", f"{symbol} {total:,.0f}")
            st.caption("Estimate excludes flights and local transportation.")
        with col_transport:
            st.markdown("### Transit Guide")
            transport = data.get("transport", {})
            for app in transport.get("ride_apps", []):
                st.link_button(
                    f"Search & Download {app}",
                    f"https://www.google.com/search?q={urllib.parse.quote(app)}",
                    key=f"ride_{app}",
                    use_container_width=True,
                )
            st.write(transport.get("public_transit", "No transit information returned."))

    st.markdown("---")
    st.caption("Prices and service availability are estimates. Please verify before traveling.")


col_logo, col_title = st.columns([1, 7])
with col_logo:
    if os.path.exists("src/logo.png"):
        st.image("src/logo.png", width=120)
with col_title:
    st.markdown(
        """
        <div style="margin-top: 5px;">
            <h1 class="header-title">Trip Planner AI</h1>
            <p class="header-subtitle">Premium intelligent travel planner and route concierge</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

with st.container():
    st.markdown("### Trip Parameters")
    col_country, col_city = st.columns(2)
    with col_country:
        country_selection = st.selectbox("Destination Country", list(COUNTRIES_AND_CITIES.keys()))
    with col_city:
        if country_selection != "Other":
            city_selection = st.selectbox("Destination City", COUNTRIES_AND_CITIES[country_selection])
            custom_country = ""
            custom_city = ""
        else:
            custom_country = st.text_input("Enter Country Name", placeholder="e.g. Canada")
            custom_city = st.text_input("Enter City Name", placeholder="e.g. Toronto")
            city_selection = ""

    col_travelers, col_days = st.columns(2)
    with col_travelers:
        travelers = st.number_input("Number of Travelers", min_value=1, value=1)
    with col_days:
        days = st.number_input("Number of Days", min_value=1, value=1)

    submitted = st.button(label="Plan My Trip", type="primary")

if submitted:
    if country_selection == "Other":
        destination = f"{custom_city.strip()}, {custom_country.strip()}".strip(", ")
        if not custom_city.strip() or not custom_country.strip():
            st.error("Please enter a valid country and city name.")
            st.stop()
    else:
        destination = f"{city_selection}, {country_selection}"

    defaults = demo_trip_data(destination)
    with st.status("Planning your trip...", expanded=True) as status:
        status.write("Finding hotels, restaurants, attractions, and transit options...")
        trip_data = ask_mistral(destination, defaults)
        trip_data["destination"] = destination
        trip_data["travelers"] = int(travelers)
        trip_data["days"] = int(days)
        st.session_state["trip_results"] = trip_data
        status.update(label="Trip planning completed.", state="complete")

if st.session_state.get("trip_results"):
    saved = st.session_state["trip_results"]
    render_trip(saved, saved.get("travelers", travelers), saved.get("days", days))

st.markdown(
    """
    <div class="footer-container">
        <p class="footer-credit">Designed & Developed by <span class="footer-name">Muhammad Umar Faiz</span></p>
    </div>
    """,
    unsafe_allow_html=True,
)
