import streamlit as st
from google import genai

# Setup the client
client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

st.title("🕵️‍♂️ Gemini API Model Debugger")
st.write("Click the button below to ask Google which models your API key can see.")

if st.button("Fetch Available Models"):
    try:
        st.info("Fetching models from Google...")
        # This is the exact command to list models in the new SDK
        models = client.models.list()
        
        # Create a clean list to display
        model_names = [m.name for m in models]
        
        if model_names:
            st.success("Successfully fetched models!")
            st.write("### Your Approved Models:")
            for name in model_names:
                st.code(name) # This prints it in a copy-pasteable box
        else:
            st.warning("Google returned an empty list. Your key has no model access.")
            
    except Exception as e:
        st.error(f"Connection Error: {str(e)}")
