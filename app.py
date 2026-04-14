import streamlit as st
from google import genai
import pandas as pd

# 1. Setup & Security
# Using the NEW Google GenAI library
client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

st.set_page_config(page_title="MSAFinancials Analyst", layout="wide")
st.title("📈 MSAFinancials: Professional Treasury Analyst")

# 2. Initialize Session State
if "raw_data" not in st.session_state:
    st.session_state.raw_data = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# 3. File Upload & Cleaning
uploaded_file = st.file_uploader("Upload bank statement (CSV)", type=["csv"]) 

if uploaded_file is not None and st.session_state.raw_data is None:
    df = pd.read_csv(uploaded_file)
    if 'Amount' in df.columns:
        df['Amount'] = df['Amount'].astype(str).str.replace('€', '', regex=False).str.replace(' ', '', regex=False)
        def clean_currency(val):
            if ',' in val and '.' in val: return val.replace('.', '').replace(',', '.')
            if ',' in val: return val.replace(',', '.')
            return val
        df['Amount'] = df['Amount'].apply(clean_currency)
        df['Amount'] = pd.to_numeric(df['Amount'], errors='coerce')
        df = df.dropna(subset=['Amount'])
    st.session_state.raw_data = df
    st.success("Data loaded!")

# 4. Analysis Section
if st.session_state.raw_data is not None:
    df = st.session_state.raw_data
    total_in = df[df['Amount'] > 0]['Amount'].sum()
    total_out = df[df['Amount'] < 0]['Amount'].sum()
    net_cashflow = total_in + total_out
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Inflow", f"€{total_in:,.2f}")
    col2.metric("Total Outflow", f"€{abs(total_out):,.2f}", delta_color="inverse")
    col3.metric("Net Cashflow", f"€{net_cashflow:,.2f}")

    st.divider()
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Ask about your finances..."):
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # The perfectly formatted prompt with rounded decimals and strict persona instructions
        full_prompt = f"""
        CONTEXT: 
        You are a witty, professional Senior Treasury Analyst at MSAFinancials helping the user analyze their bank statement.
        
        DATA:
        - Total Inflow: €{total_in:.2f}
        - Total Outflow: €{total_out:.2f}
        - Net Cashflow: €{net_cashflow:.2f}
        
        INSTRUCTIONS:
        1. Answer the user's question directly.
        2. Do NOT simply repeat the data back to the user unless they ask for it.
        3. If the user just says "hello" or greets you, greet them back professionally, mention their current Net Cashflow briefly, and ask how you can help them analyze their spending.
        4. Reject non-financial questions firmly but politely.
        
        USER QUESTION: 
        {prompt}
        """
        
        try:
            # We use the exact string from your approved list
            response = client.models.generate_content(
                model="gemini-2.5-flash", 
                contents=full_prompt
            )
            
            st.session_state.chat_history.append({"role": "assistant", "content": response.text})
            with st.chat_message("assistant"):
                st.markdown(response.text)
        except Exception as e:
            st.error(f"AI Connection Error: {str(e)}")
