import streamlit as st
from google import genai
import pandas as pd
import re

# 1. Setup & Security
client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

st.set_page_config(page_title="MSAFinancials Analyst", layout="wide", initial_sidebar_state="expanded")

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

# 3. File Upload & Data Pipeline
uploaded_file = st.file_uploader("Upload bank statement (CSV)", type=["csv"]) 

if uploaded_file is not None and st.session_state.raw_data is None:
    df = pd.read_csv(uploaded_file)
    
    # Currency Auto-Detection
    raw_text_dump = df.to_string().lower()
    if any(indicator in raw_text_dump for indicator in ['inr', 'rs.', '₹', 'rupee', 'gurugram', 'mumbai', 'delhi']):
        st.session_state.auto_currency = "₹"
        st.rerun() 
    elif any(indicator in raw_text_dump for indicator in ['usd', '$']):
        st.session_state.auto_currency = "$"
        st.rerun()
    
    original_cols = df.columns.tolist()
    lower_cols = [str(c).lower().strip() for c in original_cols]
    df.columns = lower_cols
    
    def clean_currency(val):
        if pd.isna(val): return 0.0
        val = str(val).strip()
        val = re.sub(r'[^\d\.,\-]', '', val)
        if val == '': return 0.0
        
        last_comma = val.rfind(',')
        last_dot = val.rfind('.')
        if last_comma > last_dot and last_dot != -1:
            val = val.replace('.', '').replace(',', '.') 
        else:
            val = val.replace(',', '') 
        try: return float(val)
        except: return 0.0

    # Auto-detect transaction type (CR/DR)
    type_col = next((c for c in lower_cols if any(k in c for k in ['type', 'cr/dr', 'dr/cr', 'cr or dr'])), None)
    amt_col = next((c for c in lower_cols if any(k in c for k in ['amount', 'txn amount', 'transaction amount'])), None)

    if amt_col and type_col:
        df['Amount'] = df[amt_col].apply(clean_currency)
        df['Amount'] = df.apply(lambda row: -abs(row['Amount']) if 'dr' in str(row[type_col]).lower() or 'debit' in str(row[type_col]).lower() else abs(row['Amount']), axis=1)
    elif amt_col:
        df['Amount'] = df[amt_col].apply(clean_currency)
    else:
        dep_col = next((c for c in lower_cols if any(k in c for k in ['deposit', 'credit', 'cr', 'in'])), None)
        wit_col = next((c for c in lower_cols if any(k in c for k in ['withdrawal', 'debit', 'dr', 'out'])), None)
        
        if dep_col or wit_col:
            deposits = df[dep_col].apply(clean_currency) if dep_col else 0
            withdrawals = df[wit_col].apply(clean_currency) if wit_col else 0
            df['Amount'] = deposits - withdrawals

    # Description Parsing & Categorization
    desc_col = next((c for c in lower_cols if any(k in c for k in ['description', 'narration', 'particulars', 'remarks'])), None)

    if desc_col:
        def extract_description(text):
            if pd.isna(text): return "Unknown"
            text = str(text).lower()
            parts = re.split(r'[\/\-\@]', text) 
            ignore = ['upi', 'nfs', 'cash', 'wdl', 'bank', 'ltd', 'payments', 'oid', 'payvia', 'imps', 'neft', 'rtgs']
            cleaned = [p.strip() for p in parts if p.strip() and p.strip() not in ignore and not p.strip().isnumeric()]
            return " ".join(cleaned[:3]).title()

        def categorize(desc):
            desc = desc.lower()
            if any(x in desc for x in ['zomato', 'swiggy', 'restaurant', 'cafe', 'blinkit', 'zepto', 'food']):
                return 'Food & Groceries'
            elif any(x in desc for x in ['medical', 'pharmacy', 'medicines', 'hospital', 'clinic']):
                return 'Health'
            elif any(x in desc for x in ['cash', 'atm', 'wdl']):
                return 'Cash Withdrawal'
            elif any(x in desc for x in ['paytm', 'razorpay', 'phonepe', 'gpay', 'upi']):
                return 'Transfers/Wallets'
            elif any(x in desc for x in ['rent', 'landlord', 'estate']):
                return 'Rent'
            elif any(x in desc for x in ['uber', 'ola', 'rapido', 'metro', 'irctc', 'flights']):
                return 'Transport'
            else:
                return 'Others'

        df['Clean_Description'] = df[desc_col].apply(extract_description)
        df['Category'] = df['Clean_Description'].apply(categorize)

    if 'Amount' in df.columns:
        df = df[df['Amount'] != 0]
        st.session_state.raw_data = df
        st.success("Bank statement successfully parsed, cleaned, and mapped!")
    else:
        st.error("Could not auto-detect data structure. Please check your CSV.")

# 4. Analysis Section
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

    # --- THE DETERMINISTIC MATH ENGINE ---
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

    if prompt := st.chat_input("Ask about your finances..."):
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
        
        # --- MODEL FALLBACK PIPELINE ---
        fallback_models = [
            "gemini-2.5-flash",
            "gemini-2.0-flash", 
            "gemini-1.5-flash"
        ]
        
        response = None
        error_msgs = []

        with st.spinner("Analyzing..."):
            for model_name in fallback_models:
                try:
                    response = client.models.generate_content(
                        model=model_name, 
                        contents=full_prompt
                    )
                    break # Success! Exit the loop
                except Exception as e:
                    error_msgs.append(f"{model_name} failed.")
                    continue # Try the next model
            
        if response:
            st.session_state.chat_history.append({"role": "assistant", "content": response.text})
            with st.chat_message("assistant"):
                st.markdown(response.text)
        else:
            st.error("AI Connection Failed across all fallback models. Please check your API quota or network connection.")
            with st.expander("Show Error Details"):
                for err in error_msgs:
                    st.write(err)
