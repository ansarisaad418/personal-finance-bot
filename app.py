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
uploaded_file = st.file_uploader("Upload bank statement (CSV/PDF)", type=["csv"]) 

# Note: We're starting with CSV as it's cleaner for Python math. 
# We'll add the PDF-to-CSV converter logic once the math is stable.

if uploaded_file is not None and st.session_state.raw_data is None:
    df = pd.read_csv(uploaded_file)
    
    # Cleaning "Amount" for Python math
    # Converts European "1.234,56" to "1234.56"
    if df['Amount'].dtype == object:
        df['Amount'] = df['Amount'].str.replace('.', '', regex=False).str.replace(',', '.', regex=False).astype(float)
    
    st.session_state.raw_data = df
    st.success("Data loaded and structured successfully!")

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
        
        full_prompt = f"""
        User Data Summary: {data_summary}
        Chat History: {st.session_state.chat_history[-3:]} 
        User Question: {prompt}
        
        Instruction: You are a professional Treasury Analyst. Use the math provided above. 
        If the question is unrelated to finance, politely decline.
        """
        
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(full_prompt)
        
        # Add AI response to history
        st.session_state.chat_history.append({"role": "assistant", "content": response.text})
        with st.chat_message("assistant"):
            st.markdown(response.text)
