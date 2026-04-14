import streamlit as st
import google.generativeai as genai
import pandas as pd

# 1. Setup & Security
# Force the library to use the stable V1 API to avoid the 404 error
genai.configure(api_key=st.secrets["GEMINI_API_KEY"], transport='grpc') 

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
    df = pd.read_csv(uploaded_file)
    
    # Robust Cleaning Logic
    if 'Amount' in df.columns:
        df['Amount'] = df['Amount'].astype(str).str.replace('€', '', regex=False).str.replace(' ', '', regex=False)
        
        def clean_currency(val):
            if ',' in val and '.' in val:
                return val.replace('.', '').replace(',', '.')
            elif ',' in val:
                return val.replace(',', '.')
            return val

        df['Amount'] = df['Amount'].apply(clean_currency)
        df['Amount'] = pd.to_numeric(df['Amount'], errors='coerce')
        df = df.dropna(subset=['Amount'])
    
    st.session_state.raw_data = df
    st.success("Data successfully cleaned and loaded!")

# 4. Deterministic Math & AI Section
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

    st.divider()
    st.subheader("Interactive Financial Analysis")

    # Display Chat History
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # 5. The Chat Input & AI Logic
    if prompt := st.chat_input("Ask about your transactions..."):
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Prepare context
        data_summary = df.describe(include='all').to_string() 
        
        full_prompt = f"""
        CONTEXT:
        You are a Senior Treasury Analyst at MSAFinancials. 
        
        PYTHON-CALCULATED DATA:
        - Total Inflow: {total_in}
        - Total Outflow: {total_out}
        - Net Cashflow: {net_cashflow}
        
        DATA SUMMARY:
        {data_summary}
        
        USER QUESTION: 
        {prompt}
        
        INSTRUCTIONS:
        1. Use the data to provide professional financial insights.
        2. Maintain a professional, witty, yet firm tone.
        3. Reject non-financial questions with: "Stupid bot error: I cannot talk about anything unrelated to your finances."
        """
        
        # Call Gemini with proper indentation
        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(full_prompt)
            
            st.session_state.chat_history.append({"role": "assistant", "content": response.text})
            with st.chat_message("assistant"):
                st.markdown(response.text)
        except Exception as e:
            st.error(f"AI Connection Error: {str(e)}")
