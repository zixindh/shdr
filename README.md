# Shanghai Disney Resort Guide

A minimalistic Streamlit app serving as a public wiki for Shanghai Disney Resort guests, featuring an AI chat assistant powered by Gemini 2.5 Flash.

## Features

- 🏠 **Overview**: General information about the resort
- 🎢 **Attractions**: Detailed information about all park attractions organized by lands
- 🍽️ **Dining**: Restaurant and food service options
- 🕐 **Hours & Tickets**: Operating hours and ticket information
- 💬 **AI Assistant**: Chat interface powered by Gemini AI

## Setup

1. Clone this repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. For the AI chat feature, you'll need a Gemini API key:
   - Get your API key from [Google AI Studio](https://makersuite.google.com/app/apikey)
   - **For local development:** Set the environment variable:
     ```bash
     export GEMINI_API_KEY=your_api_key_here
     ```
   - **For Streamlit Cloud:** Add `GEMINI_API_KEY` to your app's secrets

## Deployment to Streamlit Cloud

1. Push this code to a GitHub repository
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your GitHub repository
4. Add your `GEMINI_API_KEY` in the Secrets section
5. Deploy!

## Data Sources

This app uses information from official Shanghai Disneyland Resort sources and public documentation to ensure accuracy and reliability.

## License

This project is for educational and informational purposes.
