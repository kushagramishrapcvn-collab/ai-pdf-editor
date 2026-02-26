import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader
from fpdf import FPDF
import io

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="AI PDF Editor", page_icon="📄")
st.title("📄 AI PDF Editor")
st.markdown("Upload a PDF and tell the AI how to edit or summarize it.")

# Enter your Google Gemini API Key here
API_KEY = "AIzaSyB9jSkAQjZZm-UTyz0apVBtdShCwrT_YjQ"
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-pro')

# --- 2. THE UI (The Website Part) ---
uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")
user_command = st.text_area("AI Command", placeholder="e.g., 'Extract all trigonometry formulas and simplify them' or 'Summarize page 1'")

if st.button("Process & Edit PDF"):
    if uploaded_file is not None and user_command:
        with st.spinner("AI is thinking..."):
            try:
                # Read the PDF
                reader = PdfReader(uploaded_file)
                original_text = ""
                for page in reader.pages:
                    original_text += page.extract_text()

                # Send to AI
                prompt = f"Context: {original_text}\n\nTask: {user_command}\n\nPlease provide the edited text content for a new PDF document."
                response = model.generate_content(prompt)
                edited_text = response.text

                # Create New PDF
                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Arial", size=12)
                # Ensure text fits PDF encoding
                clean_text = edited_text.encode('latin-1', 'replace').decode('latin-1')
                pdf.multi_cell(0, 10, clean_text)
                
                # Output to a buffer so the user can download it
                pdf_output = pdf.output(dest='S').encode('latin-1')
                
                st.success("Done! Your edited PDF is ready.")
                st.download_button(
                    label="Download Edited PDF",
                    data=pdf_output,
                    file_name="edited_document.pdf",
                    mime="application/pdf"
                )
            except Exception as e:
                st.error(f"An error occurred: {e}")
    else:
        st.warning("Please upload a file and type a command first!")
