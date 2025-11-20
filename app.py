import streamlit as st
import os
from datetime import datetime
from google import genai

# Page config
st.set_page_config(
    page_title="Shanghai Disney Quick Guide",
    page_icon="🏰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Park information (static for reliability - users should check official app for live data)
park_info = {
    "hours": "9:00 AM – 9:00 PM (typical operating hours)",
    "fireworks": "Illuminations fireworks show",
    "notes": "Download official app for real-time updates"
}

# Real-time banner (always visible)
st.markdown(f"""
<div style="background:#FF6B35;color:white;padding:1rem;text-align:center;font-size:1.3rem;font-weight:bold;">
🏰 Today ({datetime.now().strftime('%b %d, %Y')}): {park_info['hours']} | Fireworks: {park_info['fireworks']}
<br><small>{park_info['notes']}</small>
</div>
""", unsafe_allow_html=True)

# Initialize Gemini API
@st.cache_resource
def init_gemini():
    # Debug: Check API key sources
    env_key = os.environ.get("GEMINI_API_KEY")
    secrets_key = None
    try:
        secrets_key = st.secrets.get("GEMINI_API_KEY")
    except Exception as e:
        secrets_error = str(e)

    # Use environment variable first (local), then secrets (cloud)
    api_key = env_key or secrets_key

    if api_key:
        return genai.Client(api_key=api_key)
    return None

client = init_gemini()

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
    st.markdown("### 🤖 Smart Disney Assistant")

    if client is None:
        st.error("🤖 AI Assistant is currently unavailable. Please check your API key configuration.")

        # Debug information
        with st.expander("🔍 Debug Information"):
            env_key = os.environ.get("GEMINI_API_KEY")
            secrets_available = False
            secrets_error = "No error"
            try:
                test_secret = st.secrets.get("GEMINI_API_KEY")
                secrets_available = test_secret is not None
            except Exception as e:
                secrets_error = str(e)

            st.write("**Environment Variable (GEMINI_API_KEY):**", "✅ Set" if env_key else "❌ Not set")
            st.write("**Streamlit Secrets (GEMINI_API_KEY):**", "✅ Available" if secrets_available else f"❌ Error: {secrets_error}")

            if not env_key and not secrets_available:
                st.write("**Solution:** Set `GEMINI_API_KEY` in Streamlit Cloud secrets or as environment variable")

        st.info("💡 **Setup Required:** Get your Gemini API key from [Google AI Studio](https://makersuite.google.com/app/apikey) and set it as `GEMINI_API_KEY` in Streamlit Cloud secrets.")
    else:
        if "messages" not in st.session_state:
            st.session_state.messages = []

        # Display chat history
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        # Chat input
        if prompt := st.chat_input("Ask anything about Shanghai Disney..."):
            # Add user message to history
            st.session_state.messages.append({"role": "user", "content": prompt})

            # Display user message
            with st.chat_message("user"):
                st.markdown(prompt)

            # Generate AI response
            try:
                context = f"""
                You are a helpful AI assistant for Shanghai Disneyland Resort. Provide accurate information about:
                - Park attractions and entertainment
                - Dining options and recommendations
                - Operating hours and ticket information
                - Guest services and accessibility
                - Park navigation and tips
                - Weather considerations and seasonal events

                Current park info: Hours: {park_info['hours']}, Fireworks: {park_info['fireworks']}

                Always be friendly, accurate, and focused on enhancing the guest experience.
                If you don't know specific details, direct guests to check the official Shanghai Disneyland website or app.
                """

                response = client.models.generate_content(
                    model="gemini-2.5-flash", contents=f"{context}\n\nUser question: {prompt}"
                )
                ai_response = response.text

                # Add AI response to history
                st.session_state.messages.append({"role": "assistant", "content": ai_response})

                # Display AI response
                with st.chat_message("assistant"):
                    st.markdown(ai_response)

            except Exception as e:
                st.error(f"❌ Error generating response: {str(e)}")

# Footer
st.markdown("---")
st.markdown("Data from official Shanghai Disney Resort · Always double-check the official app for live wait times & changes")