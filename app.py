import streamlit as st
import google.generativeai as genai
import pandas as pd
import re

# 1. Setup & Security
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

st.set_page_config(page_title="FinSight Analyst", layout="wide")
st.title("📈 FinSight: Professional Treasury Analyst")

# 2. Initialize Session State (Memory)
if "raw_data" not in st.session_state:
    st.session_state.raw_data = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# 3. File Upload
uploaded_file = st.file_uploader("Upload bank statement (CSV)", type=["csv"]) 

if uploaded_file is not None and st.session_state.raw_data is None:
    df = pd.read_csv(uploaded_file)
    
    # NEW ROBUST CLEANING LOGIC
    if 'Amount' in df.columns:
        # 1. Convert to string just in case
        df['Amount'] = df['Amount'].astype(str)
        # 2. Remove currency symbols and spaces
        df['Amount'] = df['Amount'].str.replace('€', '', regex=False).str.replace(' ', '', regex=False)
        # 3. Handle European format: "1.234,56" -> "1234.56"
        # We replace the thousands-separator (.) with nothing, then the decimal (,) with a (.)
        if df['Amount'].str.contains(',').any() and df['Amount'].str.contains('.').any():
             df['Amount'] = df['Amount'].str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
        elif df['Amount'].str.contains(',').any():
             df['Amount'] = df['Amount'].str.replace(',', '.', regex=False)
             
        # 4. Final conversion to a real number (float)
        df['Amount'] = pd.to_numeric(df['Amount'], errors='coerce')
        
        # 5. Drop any rows where Amount couldn't be converted
        df = df.dropna(subset=['Amount'])
    
    st.session_state.raw_data = df
    st.success("Data cleaned and loaded!")

# 4. Deterministic Math (Python does the counting)
if st.session_state.raw_data is not None:
    df = st.session_state.raw_data
    
    total_in = df[df['Amount'] > 0]['Amount'].sum()
    total_out = df[df['Amount'] < 0]['Amount'].sum()
    net_cashflow = total_in + total_out
    
    # Display Metrics
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Inflow", f"€{total_in:,.2f}")
    col2.metric("Total Outflow", f"€{abs(total_out):,.2f}", delta_color="inverse")
    col3.metric("Net Cashflow", f"€{net_cashflow:,.2f}")

    # 5. AI Contextual Analysis
    st.divider()
    st.subheader("Interactive Financial Analysis")

    # Display Chat History
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Ask about your spending..."):
        # Add user message to history
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Send math context + prompt to Gemini
        # We only send a summary of data to save tokens/efficiency
        data_summary = df.describe().to_string() 
        
       # Optimized for a professional Treasury Analyst persona
        full_prompt = f"""
        CONTEXT:
        You are a Senior Treasury Analyst. You have a detailed summary of the user's financial transactions.
        
        DATA SUMMARY (Python-calculated):
        {data_summary}
        
        CONVERSATION LOG:
        {st.session_state.chat_history[-3:]} 
        
        USER QUESTION: 
        {prompt}
        
        INSTRUCTIONS:
        1. Use the DATA SUMMARY to provide exact figures.
        2. If the user asks about savings, look at positive inflows vs fixed outflows.
        3. Maintain a professional, witty, yet firm tone.
        4. If the question is non-financial, trigger the error: "Stupid bot error: I cannot talk about anything unrelated to your finances."
        """
        
        # Use the explicit model path
        model = genai.GenerativeModel('models/gemini-1.5-flash')
        response = model.generate_content(full_prompt)
