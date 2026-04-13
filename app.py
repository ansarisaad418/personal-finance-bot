import streamlit as st
import google.generativeai as genai
import pandas as pd

# 1. Setup & Security
# Ensure 'GEMINI_API_KEY' is set in your Streamlit Cloud Secrets
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

st.set_page_config(page_title="MSAFinancials Analyst", layout="wide")
st.title("📈 MSAFinancials: Professional Treasury Analyst")

# 2. Initialize Session State (Memory)
if "raw_data" not in st.session_state:
    st.session_state.raw_data = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# 3. File Upload
uploaded_file = st.file_uploader("Upload bank statement (CSV)", type=["csv"]) 

if uploaded_file is not None and st.session_state.raw_data is None:
    # Read the CSV
    df = pd.read_csv(uploaded_file)
    
    # NEW ROBUST CLEANING LOGIC for Amount column
    if 'Amount' in df.columns:
        # Convert to string and strip spaces/symbols
        df['Amount'] = df['Amount'].astype(str).str.replace('€', '', regex=False).str.replace(' ', '', regex=False)
        
        # Handle European format: "1.234,56" -> "1234.56"
        def clean_currency(val):
            if ',' in val and '.' in val:
                return val.replace('.', '').replace(',', '.')
            elif ',' in val:
                return val.replace(',', '.')
            return val

        df['Amount'] = df['Amount'].apply(clean_currency)
        
        # Final conversion to a real number (float)
        df['Amount'] = pd.to_numeric(df['Amount'], errors='coerce')
        
        # Drop rows that aren't financial data (headers/footers)
        df = df.dropna(subset=['Amount'])
    
    st.session_state.raw_data = df
    st.success("Data successfully cleaned and structured!")

# 4. Deterministic Math (Python-calculated Metrics)
if st.session_state.raw_data is not None:
    df = st.session_state.raw_data
    
    total_in = df[df['Amount'] > 0]['Amount'].sum()
    total_out = df[df['Amount'] < 0]['Amount'].sum()
    net_cashflow = total_in + total_out
    
    # Display Metrics Cards
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Inflow", f"€{total_in:,.2f}")
    col2.metric("Total Outflow", f"€{abs(total_out):,.2f}", delta_color="inverse")
    col3.metric("Net Cashflow", f"€{net_cashflow:,.2f}")

    # 5. AI Analysis Section
    st.divider()
    st.subheader("Interactive Financial Analysis")

    # Display Chat History Bubble
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Ask about your transactions..."):
        # Add user message to history
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Prepare context for AI
        # We send the statistical summary and the column names to keep it efficient
        data_summary = df.describe(include='all').to_string() 
        
        full_prompt = f"""
        CONTEXT:
        You are a Senior Treasury Analyst at MSAFinancials. You are reviewing the user's uploaded statement.
        
        PYTHON-CALCULATED SUMMARY:
        {data_summary}
        
        RECENT CHAT HISTORY:
        {st.session_state.chat_history[-3:]} 
        
        USER QUESTION: 
        {prompt}
        
        INSTRUCTIONS:
        1. Use the DATA SUMMARY to provide exact figures (Total In: {total_in}, Total Out: {total_out}).
        2. If the user asks about specific categories or savings, analyze the data provided.
        3. Maintain a professional, witty, yet firm tone.
        4. If the question is non-financial, trigger the error: "Stupid bot error: I cannot talk about anything unrelated to your finances."
        """
        
        # Call Gemini Brain
        model = genai.GenerativeModel('models/gemini-1.5-flash')
        response = model.generate_content(full_prompt)
        
        # Display AI response and save to history
        st.session_state.chat_history.append({"role": "assistant", "content": response.text})
        with st.chat_message("assistant"):
            st.markdown(response.text)
