import streamlit as st
from google import genai  # Modern 2026 SDK
from pypdf import PdfReader
from fpdf import FPDF
import io

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="AI PDF Editor 2026", page_icon="📄")
st.title("📄 AI PDF Editor")

# Use the Secret you set up in Streamlit Settings
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
    client = genai.Client(api_key=API_KEY)
except Exception:
    st.error("API Key missing! Please add 'GEMINI_API_KEY' to your Streamlit Secrets.")
    st.stop()

# --- 2. THE UI ---
uploaded_file = st.file_uploader("Upload your Math/Data PDF", type="pdf")
user_command = st.text_area("What should the AI do?", placeholder="e.g. 'Solve the calculus limits on page 2' or 'Summarize the conics section'")

if st.button("Process & Edit PDF"):
    if uploaded_file is not None and user_command:
        with st.spinner("Gemini 3 Flash is analyzing your data..."):
            try:
                # 1. Extract Text
                reader = PdfReader(uploaded_file)
                original_text = "\n".join([page.extract_text() for page in reader.pages])

                # 2. Call the 2026 Model (gemini-2.5-flash is the stable workhorse)
                # If you want the ultra-new preview, use 'gemini-3-flash-preview'
                response = client.models.generate_content(
    model='gemini-2.5-flash',
    config={
        "system_instruction": "You are a helpful academic assistant. Do not use Markdown code blocks or backticks. Write in plain, clear human language. Use bullet points for steps and clearly labeled sections for math problems."
    },
    contents=f"Document Content: {original_text}\n\nTask: {user_command}"
)
                )
                edited_text = response.text

                st.subheader("AI Preview (Human Language)")
                st.markdown(edited_text) # This shows bold, tables, and math nicely!
                st.divider()
                
                # --- PDF CREATION STARTS HERE ---
                pdf = FPDF()
                # ... (rest of your PDF code)
                # 3. Create New PDF
                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Arial", size=12)
                
                # Clean text for PDF (removes math symbols FPDF can't handle)
                clean_text = edited_text.encode('latin-1', 'replace').decode('latin-1')
                pdf.multi_cell(0, 10, clean_text)
                
                # CONVERSION STEP: This turns the bytearray into stable bytes
                pdf_final_data = bytes(pdf.output()) 
                
                st.success("Successfully processed!")
                st.download_button(
                    label="Download Edited PDF",
                    data=pdf_final_data, # This is now the correct <class 'bytes'>
                    file_name="ai_math_notes.pdf",
                    mime="application/pdf"
                )
            except Exception as e:
                st.error(f"Error: {e}")
