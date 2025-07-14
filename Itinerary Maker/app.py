import streamlit as st
import google.generativeai as genai
from datetime import datetime, timedelta
import json
import re
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import sqlite3
import os

# --- Configuration ---
API_KEY = "AIzaSyACMVyH2RYIlokZJ39nOjW-1a2RWzaOOE8"
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel("gemini-1.5-pro")

# --- Styling ---
st.set_page_config(page_title="Itinerary Maker", layout="wide")
st.markdown("""
    <style>
        .stApp {
            background: linear-gradient(to bottom right, #ffffff, #d0eaff);
            font-family: 'Segoe UI', sans-serif;
        }
        h1, h2, h3, h4 {
            color: #0F4C75;
        }
        .activity-card {
            background: #ffffffcc;
            border-radius: 15px;
            padding: 20px;
            margin: 15px 0;
            box-shadow: 0 6px 12px rgba(0, 0, 0, 0.1);
        }
        .activity-card h4 {
            margin-top: 0;
        }
        .activity-card p {
            margin: 5px 0;
        }
        .activity-card a {
            text-decoration: none;
            color: #3282B8;
            font-weight: bold;
        }
    </style>
""", unsafe_allow_html=True)

# --- SQLite Database Functions ---
def init_db():
    conn = sqlite3.connect("itineraries.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS itineraries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            itinerary_json TEXT
        )
    ''')
    conn.commit()
    return conn, cursor

def save_to_db(title, json_data, cursor, conn):
    cursor.execute('INSERT INTO itineraries (title, itinerary_json) VALUES (?, ?)', 
                   (title, json.dumps(json_data)))
    conn.commit()

def load_from_db(cursor):
    cursor.execute('SELECT id, title, itinerary_json FROM itineraries')
    return cursor.fetchall()

def delete_from_db(itinerary_id, cursor, conn):
    cursor.execute('DELETE FROM itineraries WHERE id = ?', (itinerary_id,))
    conn.commit()

# --- PDF Export Helper ---
def save_itinerary_pdf(itinerary, filename):
    c = canvas.Canvas(filename, pagesize=letter)
    width, height = letter
    y = height - 40
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, y, "Travel Itinerary")
    c.setFont("Helvetica", 12)

    for day in itinerary.get("days", []):
        y -= 30
        c.drawString(40, y, f"Day {day.get('day')}")
        for act in day.get("activities", []):
            y -= 20
            c.drawString(60, y, f"{act['title']} - {act['start_time']} to {act['end_time']}")
            y -= 15
            c.drawString(80, y, act['description'])
            if y < 100:
                c.showPage()
                y = height - 40
        if "accommodation" in day:
            y -= 30
            acc = day["accommodation"]
            c.drawString(60, y, f"\U0001F3E8 {acc.get('name')} - {acc.get('address')}")
            y -= 20
            c.drawString(80, y, f"Check-in: {acc.get('check_in')} | Check-out: {acc.get('check_out')}")
            if y < 100:
                c.showPage()
                y = height - 40
    c.save()

# --- Tabs ---
tab1, tab2 = st.tabs(["\U0001F30D Generate Itinerary", "💾 Saved Trips"])

# --- Tab 1: Generate Itinerary ---
with tab1:
    st.title("\U0001F30D Travel Itinerary Generator")

    city = st.text_input("Enter the city you're visiting:")
    start_date = st.date_input("Start date", value=datetime.today())
    end_date = st.date_input("End date", value=start_date + timedelta(days=2), min_value=start_date)
    days = (end_date - start_date).days

    st.subheader("Choose Your Interests:")
    preferences = []
    include_accommodation = st.checkbox("\U0001F3E8 Include Accommodation")
    include_transport = st.checkbox("🚗 Include Transport")
    include_hotels = st.checkbox("🏝 Include Hotels & Resorts")

    pref_options = {
        "🎨 Art": "art",
        "🏫 Museums": "museums",
        "🌿 Outdoor Activities": "outdoor activities",
        "🧩 Indoor Activities": "indoor activities",
        "👶 Good for Kids": "kid-friendly places",
        "🧑‍🏫 Young People": "places popular among young people"
    }

    cols = st.columns(3)
    for i, key in enumerate(pref_options.keys()):
        with cols[i % 3]:
            if st.checkbox(key):
                preferences.append(pref_options[key])

    budget = st.selectbox("💰 Budget", ["Low", "Medium", "High"])

    if st.button("🚀 Generate Itinerary"):
        if not city:
            st.warning("Please enter a city.")
        else:
            extra = f" Budget: {budget}. "
            if include_accommodation:
                extra += "Include accommodation details. "
            if include_transport:
                extra += "Include transport options. "
            if include_hotels:
                extra += "Include hotels and resorts. "

            preference_text = ", ".join(preferences) if preferences else "a general travel experience"

            prompt = f"""
            Generate a travel itinerary in JSON only, no other text.
            City: {city}, Days: {days}. Focus on: {preference_text}. {extra}
            Format:
            {{
              "days": [
                {{
                  "day": 1,
                  "activities": [{{"title": "...", "description": "...", "start_time": "...", "end_time": "...", "link": "...", "location": "..."}}]
                }}
              ]
            }}
            """

            try:
                response = model.generate_content(prompt)
                raw_text = response.text.strip()

                json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
                response_json = json.loads(json_match.group(0) if json_match else raw_text)

                st.success("✅ Itinerary Generated!")
                filename = f"{city}_{start_date}_itinerary.pdf"

                for day in response_json["days"]:
                    st.markdown(f"### 🗓️ Day {day['day']}")
                    for act in day["activities"]:
                        map_html = ""
                        if act.get('link'):
                            map_html += f'<a href="{act["link"]}" target="_blank">🔗 More Info</a>'
                        if act.get('location'):
                            if map_html:
                                map_html += ' | '
                            map_html += f'<a href="{act["location"]}" target="_blank">📍 Map</a>'

                        st.markdown(f"""<div class='activity-card'>
                            <h4>🎯 {act['title']}</h4>
                            <p><b>Description:</b> {act['description']}</p>
                            <p><b>Time:</b> {act['start_time']} - {act['end_time']}</p>
                            {map_html}
                        </div>""", unsafe_allow_html=True)

                    if "accommodation" in day:
                        acc = day["accommodation"]
                        hotel_link = f'<a href="{acc["link"]}" target="_blank">🔗 Hotel Info</a>' if acc.get("link") else ""
                        st.markdown(f"""<div class='activity-card'>
                            <h4>🏨 Accommodation</h4>
                            <p><b>Name:</b> {acc['name']}</p>
                            <p><b>Address:</b> {acc['address']}</p>
                            <p>🕒 Check-in: {acc['check_in']} | Check-out: {acc['check_out']}</p>
                            {hotel_link}
                        </div>""", unsafe_allow_html=True)

                save_itinerary_pdf(response_json, filename)
                with open(filename, "rb") as f:
                    st.download_button("📅 Download Itinerary PDF", f, file_name=filename)
                os.remove(filename)

                conn, cursor = init_db()
                title = f"{city} Trip ({start_date} to {end_date})"
                save_to_db(title, response_json, cursor, conn)
                conn.close()

            except Exception as e:
                st.error(f"❌ Failed to generate itinerary: {e}")

# --- Tab 2: Saved Trips ---
with tab2:
    st.header("💾 Saved Trips")
    conn, cursor = init_db()
    saved_trips = load_from_db(cursor)
    if not saved_trips:
        st.info("No saved trips yet.")
    else:
        for itinerary_id, title, itinerary_str in saved_trips:
            itinerary = json.loads(itinerary_str)
            with st.expander(title):
                delete_col, _ = st.columns([1, 5])
                with delete_col:
                    if st.button("🗑 Delete", key=f"delete_{itinerary_id}"):
                        delete_from_db(itinerary_id, cursor, conn)
                        st.success("Deleted! Please refresh to see changes.")
                        st.stop()

                for day in itinerary.get("days", []):
                    st.markdown(f"#### 🗓️ Day {day.get('day')}")
                    for act in day.get("activities", []):
                        map_html = ""
                        if act.get('link'):
                            map_html += f'<a href="{act["link"]}" target="_blank">🔗 More Info</a>'
                        if act.get('location'):
                            if map_html:
                                map_html += ' | '
                            map_html += f'<a href="{act["location"]}" target="_blank">📍 Map</a>'

                        st.markdown(f"""<div class='activity-card'>
                            <h4>🎯 {act['title']}</h4>
                            <p>{act['description']}</p>
                            <p><b>Time:</b> {act['start_time']} - {act['end_time']}</p>
                            {map_html}
                        </div>""", unsafe_allow_html=True)
    conn.close()
