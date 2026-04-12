import streamlit as st
import google.generativeai as genai
import PyPDF2

# Access the API Key from Streamlit's secret vault
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

st.title("💰 Strict Analyst: Finance Bot")
st.subheader("Witty insights for your financial reality.")

# File Uploader
uploaded_file = st.file_uploader("Upload your bank statement (PDF)", type="pdf")

if uploaded_file is not None:
    # Read PDF text
    reader = PyPDF2.PdfReader(uploaded_file)
    text = ""
    for page in reader.pages:
        text += page.extract_text()

    # Define the System Prompt
    system_instruction = """
    You are a 'Strict Analyst' with an MSc in Finance. 
    Analyze the uploaded transactions.
    1. Distinguish Salary from Loans/Internal Transfers.
    2. Group everything else into 'Daily Living'.
    3. Calculate Savings Rate and Cash Flow.
    4. If the user asks anything unrelated to finance, say: 'Stupid bot error: I cannot talk about anything unrelated to your finances.'
    5. Before giving the final report, identify up to 5 ambiguous transactions and ask the user for clarity.
    """

    model = genai.GenerativeModel('gemini-1.5-flash', system_instruction=system_instruction)
    
    # Simple chat interface for the 5 questions
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("Answer the bot's questions here..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        response = model.generate_content(f"Data: {text} \n User Answer: {prompt}")
        st.session_state.messages.append({"role": "assistant", "content": response.text})
        st.rerun()
