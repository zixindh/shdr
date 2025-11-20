import streamlit as st
import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import google.generativeai as genai  # Note: updated import

# Page config
st.set_page_config(
    page_title="Shanghai Disney Quick Guide",
    page_icon="🏰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# === Fetch latest park info from official site (runs on every load) ===
@st.cache_data(ttl=3600)  # Refresh max once per hour
def get_today_park_info():
    try:
        url = "https://www.shanghaidisneyresort.com/en/calendars/park-hours/"
        html = requests.get(url, timeout=10).text
        soup = BeautifulSoup(html, 'html.parser')
        
        today = datetime.now().strftime("%Y-%m-%d")
        hours_text = "Unknown today"
        fireworks = "Check official app"
        notes = ""
        
        # Find today's row (official calendar structure changes rarely)
        for row in soup.find_all("div", class_="calendarDay"):
            if today in row.text:
                hours = row.find_next("div", class_="hours").text.strip()
                hours_text = hours.replace("Shanghai Disneyland", "").strip()
                fire = row.find_next(string=lambda t: "Illumi" in t or "fireworks" in t.lower())
                if fire:
                    fireworks = fire.strip()
                note = row.find_next("div", class_="note")
                if note:
                    notes = note.text.strip()
                break
        
        return {
            "hours": hours_text,
            "fireworks": fireworks,
            "notes": notes or "No special notices"
        }
    except:
        return {"hours": "9:00 AM – 9:00 PM (typical)", "fireworks": "Check official app", "notes": "Could not fetch live data"}

park_info = get_today_park_info()

# Real-time banner (always visible)
st.markdown(f"""
<div style="background:#FF6B35;color:white;padding:1rem;text-align:center;font-size:1.3rem;font-weight:bold;">
🏰 Today ({datetime.now().strftime('%b %d, %Y')}): {park_info['hours']} | Fireworks: {park_info['fireworks']}
<br><small>{park_info['notes']}</small>
</div>
""", unsafe_allow_html=True)

# Initialize Gemini
@st.cache_resource
def init_gemini():
    try:
        api_key = st.secrets.get("GEMINI_API_KEY")
    except:
        api_key = os.environ.get("GEMINI_API_KEY")

    if api_key:
        genai.configure(api_key=api_key)
        return genai.GenerativeModel('gemini-1.5-flash')
    return None

model = init_gemini()

# Sidebar
st.sidebar.title("Quick Navigation")
page = st.sidebar.radio("Go to:", [
    "Overview", "Getting to the Park", "Attractions", "Dining", 
    "Toilets & Baby Care", "Hours & Tickets", "AI Assistant"
], label_visibility="collapsed")

st.markdown("### Shanghai Disney Quick Guide")
st.caption("Fast, no-nonsense info for busy guests · Data updated live where possible")

# ====================== PAGES ======================

if page == "Overview":
    st.write("Unique castle, TRON, Pirates battle ride. 8 lands now with Zootopia (opened 2023). Download the official Shanghai Disney Resort app for real-time wait times & map.")

if page == "Getting to the Park":
    st.markdown("### 🚇 Best Ways to Shanghai Disneyland (2025)")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Metro Line 11 (Cheapest & Most Reliable)")
        st.write("""
        - Direct to **Disney Resort Station** (terminal stop)
        - From People's Square / Nanjing Rd: ~50–70 min, ¥7
        - First train ~6:00 AM, last ~22:30
        - Exit 1 or 2 → 5–10 min walk to park gates
        - Pro tip: Buy a Shanghai Public Transportation Card or use WeChat/Alipay
        """)
    
    with col2:
        st.markdown("#### DiDi / Taxi (Fastest with luggage/kids)")
        st.write("""
        - DiDi English version works great
        - From downtown: 40–70 min, ¥80–150
        - From PVG airport: ~30–45 min, ¥150–200
        - Drop-off: Search “上海迪士尼乐园” or “Disney Car & Coach Parking Lot”
        - Early entry hotel guests: Ask for “Mickey Parking Lot” (closer)
        """)
    
    st.info("Avoid random taxis outside the resort at closing — use DiDi to avoid scams.")

if page == "Attractions":
    st.markdown("### 🎢 Must-Know Rides & Shows")
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["Mickey Ave", "Gardens", "Fantasyland", "Tomorrowland", "Treasure Cove", "Zootopia"])

    with tab1:
        st.write("**Parades & Character Greetings** - Main street with Disney parades and meet-and-greets.")

    with tab2:
        st.write("**Voyage to the Crystal Grotto** (Disney Princess dark ride) - Best for kids. Dumbo ride nearby.")

    with tab3:
        st.write("**Seven Dwarfs Mine Train** - Gentle coaster. Peter Pan's Flight. Enchanted Storybook Castle.")

    with tab4:
        st.write("**TRON Lightcycle Power Run** - Must-do! Space Mountain. Buzz Lightyear.")

    with tab5:
        st.write("**Pirates of the Caribbean: Battle for the Sunken Treasure** - Boat ride with drops.")

    with tab6:
        st.write("**Zootopia** - New land (2023). Hot dog eating contest show. Gentle rides for families.")

if page == "Dining":
    st.markdown("### 🍽️ Food Options")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Quick Service")
        st.write("- **Donald's Diner** (American burgers/hot dogs)")
        st.write("- **Royal Banquet Hall** (Chinese dishes)")
        st.write("- **Wandering Moon Teahouse** (Asian fusion)")

    with col2:
        st.markdown("#### Table Service (Reservations Recommended)")
        st.write("- **Crystal Palace Restaurant**")
        st.write("- **Walt's Restaurant**")
        st.write("- **Enchanted Tale Restaurant** (character dining)")

    st.info("Best bet: Quick service for speed. Make reservations for table service via official app.")

if page == "Toilets & Baby Care":
    st.markdown("### 🚽 Toilet Locations (Every guest asks this!)")
    st.write("""
    There are **over 30 toilet facilities** inside the park — marked on the official app map (filter → Restrooms).
    
    Quick list of the most useful ones (always clean, air-conditioned):
    - Entrance / Mickey Avenue — right after security
    - Near TRON (Tomorrowland) — biggest & least crowded
    - Behind Enchanted Storybook Castle (Fantasyland)
    - Treasure Cove — next to Pirates
    - Zootopia — near the hot-dog stand
    - Adventure Isle — near Roaring Rapids
    - Gardens of Imagination — near Dumbo
    
    **Western sitting toilets** are always available (usually 20–30% of stalls, marked with ♿ or at the back).
    
    Baby Care Centers (diaper changing, nursing, microwave):
    - Mickey Avenue (main one)
    - Fantasyland (near Alice Wonderland Maze)
    """)
    st.info("Use the official Shanghai Disney Resort app → Map → filter 'Restrooms' for GPS directions.")

if page == "Hours & Tickets":
    st.write(f"**Live today:** {park_info['hours']}")
    st.write("Tickets: Buy only on official app/site. 1-day from ¥399–¥799 depending on date.")

if page == "AI Assistant":
    st.markdown("### 🤖 Smart Disney Assistant (always knows today's hours & live info)")
    
    if not model:
        st.error("Gemini API key missing")
    else:
        if "messages" not in st.session_state:
            st.session_state.messages = []
        
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
        
        if prompt := st.chat_input("Ask anything — wait times, best toilet, food tips..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)
            
            # Build rich up-to-date context
            context = f"""
            You are an expert Shanghai Disneyland guide (November 2025+).
            TODAY'S REAL INFO:
            - Park hours: {park_info['hours']}
            - Fireworks/Night show: {park_info['fireworks']}
            - Notes: {park_info['notes']}
            
            STATIC KNOWLEDGE (from this app):
            - Toilets: Over 30 locations, marked on official app. Western toilets always available.
            - Best transport: Metro Line 11 direct or DiDi.
            - Must-do rides: TRON, Pirates Battle, Zootopia hot-dog.
            
            Be short, practical, friendly. If unsure → tell them to check official app.
            User question: {prompt}
            """
            
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    try:
                        response = model.generate_content(context)
                        ai_response = response.text
                        st.markdown(ai_response)
                        st.session_state.messages.append({"role": "assistant", "content": ai_response})
                    except Exception as e:
                        error_msg = "Sorry, I can't respond right now. Try again later!"
                        st.error(f"Error: {str(e)}")
                        st.markdown(error_msg)
                        st.session_state.messages.append({"role": "assistant", "content": error_msg})

# Footer
st.markdown("---")
st.markdown("Data from official Shanghai Disney Resort · Always double-check the official app for live wait times & changes")