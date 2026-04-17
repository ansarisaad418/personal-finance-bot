import streamlit as st
from google import genai
import pandas as pd
import plotly.express as px

# 1. Setup & Security
client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

st.set_page_config(page_title="MSAFinancials Analyst", page_icon="📈", layout="wide", initial_sidebar_state="expanded")

# 2. Initialize Session State
if "raw_data" not in st.session_state:
    st.session_state.raw_data = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# --- SIDEBAR SETTINGS ---
with st.sidebar:
    st.header("⚙️ Settings")
    if st.button("Clear Data & Restart"):
        st.session_state.raw_data = None
        st.session_state.chat_history = []
        st.rerun()

st.title("📈 MSAFinancials: Professional Financial Analyst")

# --- ONBOARDING UI & FILE UPLOAD ---
if st.session_state.raw_data is None:
    st.markdown("### 👋 Welcome to your Personal Finance AI!")
    st.info(
        "I am your intelligent financial assistant. Upload your raw bank statement, and I will automatically "
        "categorize your spending and provide a chat interface to answer questions like: \n"
        "*'How much did I spend ordering food online this month?'* or *'What is my total cash flow?'*\n\n"
        "*(Note: Currently, I only accept standard European .csv files)*"
    )
    
    st.divider()
    
    uploaded_file = st.file_uploader("Upload bank statement (CSV)", type=["csv"]) 

    if uploaded_file is not None:
        df = pd.read_csv(uploaded_file)
        
        # Original European Formatting Logic
        if 'Amount' in df.columns:
            df['Amount'] = df['Amount'].astype(str).str.replace('€', '', regex=False).str.replace(' ', '', regex=False)
            def clean_currency(val):
                if ',' in val and '.' in val: return val.replace('.', '').replace(',', '.')
                if ',' in val: return val.replace(',', '.')
                return val
            df['Amount'] = df['Amount'].apply(clean_currency)
            df['Amount'] = pd.to_numeric(df['Amount'], errors='coerce')
            df = df.dropna(subset=['Amount'])
            
            # Identify the description column (usually 'Description', 'Name', or 'Counterparty')
            desc_cols = [c for c in df.columns if c.lower() in ['description', 'name', 'counterparty', 'mededelingen']]
            target_col = desc_cols[0] if desc_cols else df.columns[0]
            
            # Basic European Categorization (Required for the Donut Chart)
            def categorize(desc):
                desc = str(desc).lower()
                if any(x in desc for x in ['albert heijn', 'jumbo', 'dirk', 'aldi', 'lidl', 'thuisbezorgd', 'uber eats']):
                    return 'Food & Groceries'
                elif any(x in desc for x in ['ns', 'gvb', 'ov-chipkaart', 'uber', 'bolt']):
                    return 'Transport'
                elif any(x in desc for x in ['tikkie', 'betaalverzoek']):
                    return 'Debt Repayment (Tikkie)'
                elif any(x in desc for x in ['huur', 'rent']):
                    return 'Rent'
                else:
                    return 'Others'

            df['Category'] = df[target_col].apply(categorize)
            
            st.session_state.raw_data = df
            st.rerun()
        else:
            st.error("Could not find an 'Amount' column. Please check your CSV format.")

# --- DASHBOARD & ANALYSIS SECTION ---
if st.session_state.raw_data is not None:
    df = st.session_state.raw_data
    sym = "€" # Hardcoded for original European app
    
    total_in = df[df['Amount'] > 0]['Amount'].sum()
    total_out = df[df['Amount'] < 0]['Amount'].sum()
    net_cashflow = total_in + total_out
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Inflow", f"{sym}{total_in:,.2f}")
    col2.metric("Total Outflow", f"{sym}{abs(total_out):,.2f}", delta_color="inverse")
    col3.metric("Net Cashflow", f"{sym}{net_cashflow:,.2f}")

    st.divider()

    # --- PLOTLY INTERACTIVE DONUT CHART ---
    if 'Category' in df.columns:
        cat_summary = df.groupby('Category')['Amount'].sum().reset_index()
        cat_summary['Amount'] = cat_summary['Amount'].round(2)
        
        expenses_df = cat_summary[cat_summary['Amount'] < 0].copy()
        expenses_df['Amount'] = expenses_df['Amount'].abs()
        
        if not expenses_df.empty:
            st.markdown("### 🍩 Spending Breakdown")
            fig = px.pie(
                expenses_df, 
                values='Amount', 
                names='Category', 
                hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Pastel
            )
            fig.update_traces(textposition='inside', textinfo='percent+label')
            fig.update_layout(margin=dict(t=20, b=20, l=20, r=20))
            st.plotly_chart(fig, use_container_width=True)
            st.divider()

        category_summary_str = cat_summary.to_csv(index=False)
        others_df = df[df['Category'] == 'Others'].head(50)
        desc_cols = [c for c in df.columns if c.lower() in ['description', 'name', 'counterparty', 'mededelingen']]
        target_col = desc_cols[0] if desc_cols else df.columns[0]
        others_str = others_df[[target_col, 'Amount']].to_csv(index=False) if not others_df.empty else "None"
    else:
        category_summary_str = "Category data unavailable."
        others_str = "N/A"

    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Ask about your finances (e.g., 'How much did I spend ordering food online?')..."):
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
