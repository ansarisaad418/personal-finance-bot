import streamlit as st
from google import genai
import pandas as pd
import re
import csv
from io import StringIO

# 1. Setup & Security
client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

st.set_page_config(page_title="MSAFinancials Analyst", page_icon="📈", layout="wide", initial_sidebar_state="expanded")

# 2. Initialize Session State
if "raw_data" not in st.session_state:
    st.session_state.raw_data = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "auto_currency" not in st.session_state:
    st.session_state.auto_currency = "€" 

# --- SIDEBAR SETTINGS ---
with st.sidebar:
    st.header("⚙️ Settings")
    st.session_state.currency_sym = st.selectbox(
        "Display Currency", 
        options=["€", "₹", "$", "£"], 
        index=["€", "₹", "$", "£"].index(st.session_state.auto_currency)
    )
    if st.button("Clear Data & Restart"):
        st.session_state.raw_data = None
        st.session_state.chat_history = []
        st.rerun()

st.title("📈 MSAFinancials: Professional Financial Analyst")

# --- ONBOARDING UI & FILE UPLOAD ---
if st.session_state.raw_data is None:
    # The "Hero" Section - Only shows before a file is uploaded
    st.markdown("### 👋 Welcome to your Personal Finance AI!")
    st.info(
        "I am your intelligent financial assistant. Upload your raw bank statement, and I will automatically "
        "stitch broken rows, categorize your spending, and provide a chat interface to answer questions like: \n"
        "*'How much did I spend on Zomato this month?'* or *'What is my total cash flow?'*"
    )
    
    colA, colB, colC = st.columns(3)
    colA.markdown("**📊 Auto-Categorization**\nInstantly tags food, transport, and health expenses.")
    colB.markdown("**🧠 AI Insights**\nChat directly with your data using Google's Gemini models.")
    colC.markdown("**🌍 Multi-Currency**\nSeamlessly handles Euros, Indian Rupees, and messy bank formats.")
    
    st.divider()
    
    uploaded_file = st.file_uploader("Upload your bank statement (CSV)", type=["csv"]) 

    if uploaded_file is not None:
        raw_text = uploaded_file.getvalue().decode('utf-8')
        
        # Currency Auto-Detection
        raw_text_dump = raw_text.lower()
        if any(indicator in raw_text_dump for indicator in ['inr', 'rs.', '₹', 'rupee', 'gurugram', 'mumbai', 'delhi']):
            st.session_state.auto_currency = "₹"
        elif any(indicator in raw_text_dump for indicator in ['usd', '$']):
            st.session_state.auto_currency = "$"
            
        reader = csv.reader(StringIO(raw_text))
        rows = list(reader)

        records = []
        # Custom ICICI / Messy CSV Stitcher
        for i in range(len(rows)):
            row = rows[i]
            if len(row) > 0 and (re.match(r'^\d{4}-\d{2}-\d{2}', row[0]) or re.match(r'^\d{2}-\d{2}-\d{4}', row[0])):
                date_val = row[0]
                nums = [val for val in row if val.strip().replace('.','',1).isdigit()]
                
                desc_parts = []
                for offset in [-1, 0, 1]:
                    if 0 <= i + offset < len(rows):
                        adj_row = rows[i + offset]
                        words = [val.strip().replace('\n', ' ') for val in adj_row if val.strip() and not val.strip().replace('.','',1).isdigit() and not re.match(r'^\d{4}-\d{2}-\d{2}', val.strip())]
                        desc_parts.extend(words)
                
                full_desc = " ".join(desc_parts)
                amount = 0.0
                if len(nums) >= 2:
                    amount = float(nums[-2]) 
                    
                records.append({'Date': date_val, 'Description': full_desc, 'Amount': amount})

        df = pd.DataFrame(records)
        
        if not df.empty:
            def extract_clean_name(text):
                text = str(text).lower()
                parts = re.split(r'[\/\-\@]', text) 
                ignore = ['upi', 'nfs', 'cash', 'wdl', 'bank', 'ltd', 'payments', 'oid', 'payvia', 'imps', 'neft', 'rtgs']
                cleaned = [p.strip() for p in parts if p.strip() and p.strip() not in ignore and not p.strip().isnumeric()]
                return " ".join(cleaned[:3]).title()
            
            df['Clean_Description'] = df['Description'].apply(extract_clean_name)
            
            df['Amount'] = df.apply(lambda row: -abs(row['Amount']) if any(x in str(row['Clean_Description']).lower() for x in ['zomato', 'blinkit', 'swiggy', 'atm', 'uber']) else abs(row['Amount']), axis=1)

            def categorize(desc):
                desc = desc.lower()
                if any(x in desc for x in ['zomato', 'swiggy', 'restaurant', 'cafe', 'blinkit', 'zepto', 'food']):
                    return 'Food & Groceries'
                elif any(x in desc for x in ['medical', 'pharmacy', 'medicines', 'hospital']):
                    return 'Health'
                elif any(x in desc for x in ['cash', 'atm', 'wdl']):
                    return 'Cash Withdrawal'
                elif any(x in desc for x in ['paytm', 'razorpay', 'phonepe', 'upi']):
                    return 'Transfers/Wallets'
                else:
                    return 'Others'

            df['Category'] = df['Clean_Description'].apply(categorize)
            
            st.session_state.raw_data = df
            st.rerun() # Refresh to hide the onboarding UI and show the dashboard
        else:
            st.error("Could not extract valid transaction data. Please check the CSV format.")

# --- DASHBOARD & ANALYSIS SECTION ---
if st.session_state.raw_data is not None:
    df = st.session_state.raw_data
    sym = st.session_state.currency_sym
    
    total_in = df[df['Amount'] > 0]['Amount'].sum()
    total_out = df[df['Amount'] < 0]['Amount'].sum()
    net_cashflow = total_in + total_out
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Inflow", f"{sym}{total_in:,.2f}")
    col2.metric("Total Outflow", f"{sym}{abs(total_out):,.2f}", delta_color="inverse")
    col3.metric("Net Cashflow", f"{sym}{net_cashflow:,.2f}")

    st.divider()

    # The Deterministic Math Engine
    if 'Category' in df.columns:
        cat_summary = df.groupby('Category')['Amount'].sum().reset_index()
        cat_summary['Amount'] = cat_summary['Amount'].round(2)
        category_summary_str = cat_summary.to_csv(index=False)
        
        others_df = df[df['Category'] == 'Others'].head(50)
        others_str = others_df[['Clean_Description', 'Amount']].to_csv(index=False) if not others_df.empty else "None"
    else:
        category_summary_str = "Category data unavailable."
        others_str = "N/A"

    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Ask about your finances (e.g., 'How much did I spend on food?')..."):
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        full_prompt = f"""
        CONTEXT: 
        You are a witty, professional Financial Analyst at MSAFinancials.
        
        DATA TOTALS:
        - Total Inflow: {sym}{total_in:.2f}
        - Total Outflow: {sym}{total_out:.2f}
        - Net Cashflow: {sym}{net_cashflow:.2f}
        
        PRE-COMPUTED CATEGORY SUMMARY:
        {category_summary_str}
        
        UNCATEGORIZED 'OTHERS' SAMPLE:
        {others_str}
        
        INSTRUCTIONS:
        1. Answer the user's question directly.
        2. If asked about a category, strictly use the PRE-COMPUTED CATEGORY SUMMARY.
        3. If asked about a specific merchant, use the UNCATEGORIZED 'OTHERS' list.
        4. Do NOT simply repeat the data back to the user unless requested.
        
        USER QUESTION: 
        {prompt}
        """
        
        # Model Fallback Pipeline
        fallback_models = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
        response = None

        with st.spinner("Analyzing..."):
            for model_name in fallback_models:
                try:
                    response = client.models.generate_content(
                        model=model_name, 
                        contents=full_prompt
                    )
                    break 
                except Exception:
                    continue 
            
        if response:
            st.session_state.chat_history.append({"role": "assistant", "content": response.text})
            with st.chat_message("assistant"):
                st.markdown(response.text)
        else:
            st.error("AI Connection Failed across all fallback models. Please check your API quota.")
