import streamlit as st
import os
from google import genai

# Page configuration
st.set_page_config(
    page_title="Shanghai Disney Guide",
    page_icon="🎢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize Gemini API
@st.cache_resource
def init_gemini():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        try:
            api_key = st.secrets.get("GEMINI_API_KEY")
        except:
            pass
    if api_key:
        return genai.Client(api_key=api_key)
    return None

client = init_gemini()

# Custom CSS for minimalistic design
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #FF6B35;
        text-align: center;
        margin-bottom: 2rem;
    }
    .section-header {
        font-size: 1.5rem;
        font-weight: bold;
        color: #2E3440;
        margin-top: 2rem;
        margin-bottom: 1rem;
    }
    .info-card {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #FF6B35;
        margin-bottom: 1rem;
    }
    .chat-container {
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 1rem;
        background-color: #fafafa;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar navigation
st.sidebar.title("🗺️ Navigation")
page = st.sidebar.radio(
    "Choose section:",
    ["🏠 Overview", "🎢 Attractions", "🍽️ Dining", "🕐 Hours & Tickets", "💬 AI Assistant"],
    label_visibility="collapsed"
)

# Main header
st.markdown('<div class="main-header">🎢 Shanghai Disney Resort Guide</div>', unsafe_allow_html=True)

# Main content based on selection
if page == "🏠 Overview":
    st.markdown('<div class="section-header">Welcome to Shanghai Disney Resort</div>', unsafe_allow_html=True)

    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown("""
        <div class="info-card">
        <h4>🌟 About Shanghai Disneyland</h4>
        <p>Shanghai Disneyland Resort is Disney's first theme park on the Chinese mainland,
        featuring unique attractions inspired by Chinese culture alongside beloved Disney classics.</p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div class="info-card">
        <h4>📍 Location & Getting There</h4>
        <p>Located in Pudong New Area, Shanghai. Easily accessible by metro, taxi, or Disney Resort shuttle.</p>
        <p><strong>Address:</strong> 310 Huangjin Road, Pudong New Area, Shanghai</p>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/4/4f/Shanghai_Disneyland_Park_-_panoramio.jpg/320px-Shanghai_Disneyland_Park_-_panoramio.jpg",
                caption="Shanghai Disneyland Resort", width='stretch')

elif page == "🎢 Attractions":
    st.markdown('<div class="section-header">Attractions & Entertainment</div>', unsafe_allow_html=True)

    # Land tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Mickey Avenue", "Gardens of Imagination", "Fantasyland", "Tomorrowland", "Treasure Cove"])

    with tab1:
        st.markdown("""
        <div class="info-card">
        <h4>🎠 Mickey Avenue</h4>
        <p>The vibrant main street welcoming guests to the park with parades, character meet-and-greets, and Disney storytelling.</p>
        <p><strong>Key Attractions:</strong> Disney Storybook Parades, Character Greetings, Fireworks Shows</p>
        </div>
        """, unsafe_allow_html=True)

    with tab2:
        st.markdown("""
        <div class="info-card">
        <h4>🌸 Gardens of Imagination</h4>
        <p>A whimsical land featuring the world's first Disney Princess-themed dark ride and interactive experiences.</p>
        <p><strong>Key Attractions:</strong> Voyage to the Crystal Grotto, Dumbo the Flying Elephant</p>
        </div>
        """, unsafe_allow_html=True)

    with tab3:
        st.markdown("""
        <div class="info-card">
        <h4>🏰 Fantasyland</h4>
        <p>Classic Disney magic with fairy tale castles, gentle rides, and character encounters.</p>
        <p><strong>Key Attractions:</strong> Enchanted Storybook Castle, Peter Pan's Flight, Seven Dwarfs Mine Train</p>
        </div>
        """, unsafe_allow_html=True)

    with tab4:
        st.markdown("""
        <div class="info-card">
        <h4>🚀 Tomorrowland</h4>
        <p>Cutting-edge technology meets Disney imagination with thrilling space-themed adventures.</p>
        <p><strong>Key Attractions:</strong> TRON Lightcycle Power Run, Space Mountain, Buzz Lightyear Planet Rescue</p>
        </div>
        """, unsafe_allow_html=True)

    with tab5:
        st.markdown("""
        <div class="info-card">
        <h4>🏴‍☠️ Treasure Cove</h4>
        <p>An adventurous pirate-themed land inspired by Disney's Pirates of the Caribbean.</p>
        <p><strong>Key Attractions:</strong> Pirates of the Caribbean: Battle for the Sunken Treasure, Explorer Canoes</p>
        </div>
        """, unsafe_allow_html=True)

elif page == "🍽️ Dining":
    st.markdown('<div class="section-header">Dining Options</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        <div class="info-card">
        <h4>🍔 Quick Service</h4>
        <p>Fast and convenient dining options throughout the park.</p>
        <ul>
        <li>Donald's Diner (American)</li>
        <li>Royal Banquet Hall (Chinese)</li>
        <li>Wandering Moon Teahouse (Asian)</li>
        </ul>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div class="info-card">
        <h4>🍽️ Table Service</h4>
        <p>Sit-down dining experiences with reservations recommended.</p>
        <ul>
        <li>Crystal Palace Restaurant</li>
        <li>Walt's Restaurant</li>
        <li>Enchanted Tale Restaurant</li>
        </ul>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("""
    <div class="info-card">
    <h4>🥤 Specialty Experiences</h4>
    <p>Unique dining experiences including character dining and themed restaurants.</p>
    </div>
    """, unsafe_allow_html=True)

elif page == "🕐 Hours & Tickets":
    st.markdown('<div class="section-header">Operating Hours & Tickets</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        <div class="info-card">
        <h4>🕐 Operating Hours</h4>
        <p>Park hours typically vary by season. Check official website for current schedule.</p>
        <p><strong>General Hours:</strong><br>
        Opening: 9:00 AM<br>
        Closing: 9:00 PM (weekdays)<br>
        Extended hours on weekends and holidays</p>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div class="info-card">
        <h4>🎫 Ticket Information</h4>
        <p>Multiple ticket options available for 1-day or multi-day visits.</p>
        <ul>
        <li>1-Day Tickets</li>
        <li>2-Day Tickets</li>
        <li>Annual Passes</li>
        <li>Park Hopper Options</li>
        </ul>
        </div>
        """, unsafe_allow_html=True)

    st.info("⚠️ Hours and ticket prices subject to change. Please check the official Shanghai Disneyland website for the most current information.")

elif page == "💬 AI Assistant":
    st.markdown('<div class="section-header">AI Guest Assistant</div>', unsafe_allow_html=True)

    if client is None:
        st.error("🤖 AI Assistant is currently unavailable.")
        st.info("💡 **Setup Required:** Get your Gemini API key from [Google AI Studio](https://makersuite.google.com/app/apikey) and set it as `GEMINI_API_KEY` environment variable locally or in Streamlit Cloud secrets.")
    else:
        st.markdown('<div class="chat-container">', unsafe_allow_html=True)

        # Initialize chat history
        if "messages" not in st.session_state:
            st.session_state.messages = []

        # Display chat history
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        # Chat input
        if prompt := st.chat_input("Ask me anything about Shanghai Disney..."):
            # Add user message to history
            st.session_state.messages.append({"role": "user", "content": prompt})

            # Display user message
            with st.chat_message("user"):
                st.markdown(prompt)

            # Generate AI response
            try:
                context = """
                You are a helpful AI assistant for Shanghai Disneyland Resort. Provide accurate information about:
                - Park attractions and entertainment
                - Dining options and recommendations
                - Operating hours and ticket information
                - Guest services and accessibility
                - Park navigation and tips
                - Weather considerations and seasonal events

                Always be friendly, accurate, and focused on enhancing the guest experience.
                If you don't know specific details, direct guests to check the official Shanghai Disneyland website.
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

        st.markdown('</div>', unsafe_allow_html=True)

# Footer
st.markdown("---")
st.markdown("📱 **Official Website:** [Shanghai Disneyland](https://www.shanghaidisneyresort.com)")
st.caption("Information subject to change. Please verify details on the official website.")
