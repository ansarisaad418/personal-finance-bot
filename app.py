import streamlit as st
from google import genai
import pandas as pd
import plotly.express as px
import re

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
        "*'What is included in my Debt Repayment?'* or *'What is my total cash flow?'*\n\n"
        "*(Note: Currently, I only accept standard European .csv files)*"
    )
    
    st.divider()
    
    uploaded_file = st.file_uploader("Upload bank statement (CSV)", type=["csv"]) 

    if uploaded_file is not None:
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
            
            # Combine all description columns
            desc_cols = [c for c in df.columns if c.lower() in ['description', 'name', 'counterparty', 'mededelingen']]
            df['Description_Clean'] = df[desc_cols].fillna('').astype(str).agg(' '.join, axis=1)
            
            # INTENT-FIRST ARCHITECTURE: Split Flows
            df['Flow'] = df['Amount'].apply(lambda x: 'Income' if x > 0 else 'Expense')
            
            def categorize_income(desc):
                desc = str(desc).lower()
                if any(x in desc for x in ['b.v.', 'b.v', ' bv', 'salary', 'salaris', 'payroll', 'flink', 'macblauw']):
                    return 'Salary'
                elif any(x in desc for x in ['tikkie', 'betaalverzoek']):
                    return 'Friends & Family'
                elif not any(x in desc for x in ['b.v.', 'b.v', ' bv', 'n.v', 'ltd', 'inc']):
                    return 'Friends & Family'
                else:
                    return 'Other Income'

            def categorize_expense(desc):
                desc = str(desc).lower()
                if any(x in desc for x in ['albert heijn', 'jumbo', 'dirk', 'aldi', 'lidl', 'thuisbezorgd', 'uber eats', 'mcdonald', 'domino', 'restaurant', 'cafe', 'supermarkt', 'slagerij', 'avondwinkel', 'india', 'food', 'bon appetit']):
                    return 'Food & Groceries'
                elif any(x in desc for x in ['ns', 'gvb', 'ov-chipkaart', 'uber', 'bolt', 'ovpay', 'shell', 'esso', 'tankstation']):
                    return 'Transport & Fuel'
                elif any(x in desc for x in ['tikkie', 'betaalverzoek', 'paypal']):
                    return 'Debt Repayment'
                elif any(x in desc for x in ['huur', 'rent']):
                    return 'Rent'
                elif any(x in desc for x in ['apple', 'google', 'lebara', 'spotify']):
                    return 'Subscriptions'
                elif re.search(r'\bbunq bv\b|\bremitly\b|\bbank fee\b', desc):
                    return 'Banking & Services'
                elif any(x in desc for x in ['tabak', 'rokertje', 'market', 'action', 'primera', 'kiosk', 'border']):
                    return 'Lifestyle & Retail'
                elif not any(x in desc for x in ['b.v.', 'b.v', ' bv', 'n.v', 'ltd', 'inc', 'sumup', 'pin', 'betaalautomaat']):
                    return 'Friends & Family'
                else:
                    return 'Others'

            df.loc[df['Flow'] == 'Income', 'Category'] = df[df['Flow'] == 'Income']['Description_Clean'].apply(categorize_income)
            df.loc[df['Flow'] == 'Expense', 'Category'] = df[df['Flow'] == 'Expense']['Description_Clean'].apply(categorize_expense)
            
            st.session_state.raw_data = df
            st.rerun()
        else:
            st.error("Could not find an 'Amount' column. Please check your CSV format.")

# --- DASHBOARD & ANALYSIS SECTION ---
if st.session_state.raw_data is not None:
    df = st.session_state.raw_data
    sym = "€" 
    
    total_in = df[df['Amount'] > 0]['Amount'].sum()
    total_out = df[df['Amount'] < 0]['Amount'].sum()
    net_cashflow = total_in + total_out
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Inflow", f"{sym}{total_in:,.2f}")
    col2.metric("Total Outflow", f"{sym}{abs(total_out):,.2f}", delta_color="inverse")
    col3.metric("Net Cashflow", f"{sym}{net_cashflow:,.2f}")

    st.divider()

    if 'Category' in df.columns:
        income_df = df[df['Flow'] == 'Income']
        expense_df = df[df['Flow'] == 'Expense']
        
        income_summary = income_df.groupby('Category')['Amount'].sum().reset_index().sort_values(by='Amount', ascending=False)
        
        expense_summary_raw = expense_df.groupby('Category')['Amount'].sum().reset_index()
        expense_summary_raw['Amount_Abs'] = expense_summary_raw['Amount'].abs()
        expense_summary = expense_summary_raw.sort_values(by='Amount_Abs', ascending=False)
        
        st.markdown("### 🍩 Cashflow Breakdown")
        
        chart_col1, chart_col2 = st.columns(2)
        
        with chart_col1:
            if not income_summary.empty:
                top_in = income_summary.iloc[0]
                st.success(f"📈 **Top Income:** {top_in['Category']} ({sym}{top_in['Amount']:,.2f})")
                fig_in = px.pie(
                    income_summary, values='Amount', names='Category', hole=0.4,
                    color_discrete_sequence=px.colors.qualitative.Safe
                )
                fig_in.update_traces(textposition='inside', textinfo='percent+label')
                fig_in.update_layout(margin=dict(t=20, b=20, l=20, r=20), showlegend=False)
                st.plotly_chart(fig_in, use_container_width=True)

        with chart_col2:
            if not expense_summary.empty:
                top_out = expense_summary.iloc[0]
                st.warning(f"📉 **Top Expense:** {top_out['Category']} ({sym}{top_out['Amount_Abs']:,.2f})")
                fig_out = px.pie(
                    expense_summary, values='Amount_Abs', names='Category', hole=0.4,
                    color_discrete_sequence=px.colors.qualitative.Pastel
                )
                fig_out.update_traces(textposition='inside', textinfo='percent+label')
                fig_out.update_layout(margin=dict(t=20, b=20, l=20, r=20), showlegend=False)
                st.plotly_chart(fig_out, use_container_width=True)

        st.divider()

        # Context Strings for AI
        inc_str = income_summary.to_csv(index=False)
        exp_str = expense_summary[['Category', 'Amount']].to_csv(index=False)
        
        # FIX: Pass a clean log of all transactions so the AI can look up names and specific items
        # We only pass essential columns to save tokens.
        transaction_log_df = df[['Flow', 'Category', 'Description_Clean', 'Amount']]
        transaction_log_str = transaction_log_df.to_csv(index=False)
    else:
        inc_str, exp_str, transaction_log_str = "N/A", "N/A", "N/A"

    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Ask about your finances..."):
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Updated prompt to instruct the AI how to use the new transaction log
        full_prompt = f"""
        CONTEXT: 
        You are a witty, professional Financial Analyst at MSAFinancials.
        
        DATA TOTALS:
        - Total Inflow: {sym}{total_in:.2f}
        - Total Outflow: {sym}{total_out:.2f}
        - Net Cashflow: {sym}{net_cashflow:.2f}
        
        PRE-COMPUTED INCOME SUMMARY:
        {inc_str}
        
        PRE-COMPUTED EXPENSE SUMMARY:
        {exp_str}
        
        RAW TRANSACTION LOG:
        {transaction_log_str}
        
        INSTRUCTIONS:
        1. Answer the user's question directly.
        2. Strictly use the PRE-COMPUTED SUMMARIES if asked for total category math.
        3. If asked about what is included in a category (like Debt Repayment), look through the RAW TRANSACTION LOG to provide exact merchant names and amounts.
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
                except Exception as e:
                    st.error(f"Failed to connect to {model_name}. Reason: {str(e)}")
                    continue 
            
        if response:
            st.session_state.chat_history.append({"role": "assistant", "content": response.text})
            with st.chat_message("assistant"):
                st.markdown(response.text)
