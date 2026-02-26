import streamlit as st
from google import genai  # Modern 2026 SDK
from pypdf import PdfReader
from fpdf import FPDF
import io
import os

# ... inside your 'try' block after creating the pdf object ...
pdf = FPDF()

# Get the path to the font file in the current directory
font_path = os.path.join(os.getcwd(), "DejaVuSans-Bold.ttf")

if os.path.exists(font_path):
    pdf.add_font("DejaVu", "", font_path)
    pdf.set_font("DejaVu", size=12)
else:
    st.error("Font file still missing on server! Using Arial fallback.")
    pdf.set_font("Arial", size=12)

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

                # 2. Call the AI with System Instructions (ENSURE ALIGNMENT HERE)
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    config={
                        "system_instruction": "You are a helpful academic assistant. Write in plain, clear human language. Use bullet points and clearly labeled sections."
                    },
                    contents=f"Document Content: {original_text}\n\nTask: {user_command}"
                )
                
                edited_text = response.text

                # 3. Live Preview (Looks great because the browser handles Unicode)
                st.subheader("AI Analysis")
                st.markdown(edited_text)
                
                # 4. Create PDF with Unicode Support
                pdf = FPDF()
                # Add this after pdf = FPDF()
                pdf.add_font('DejaVu', '', 'DejaVuSans-Bold.ttf', uni=True)
                pdf.set_font('DejaVu', '', 12)
                pdf.add_page()
                
                # Use a built-in font that supports more symbols, or 
                # for 100% math accuracy, we use 'utf-8' handling:
                pdf.set_font("Arial", size=12) 
                
                # NEW CLEANING LOGIC:
                # 1. Remove Markdown symbols
                pdf_ready_text = edited_text.replace("**", "").replace("###", "").replace("##", "").replace("_", "")
                
                # 2. FIX THE QUESTION MARKS: 
                # Instead of 'latin-1' (which breaks math), we use 'keep' or a safer encoding
                # We use a multi_cell that handles the string directly
                try:
                    # In fpdf2 (2026 version), we don't need to manually encode/decode
                    # as long as we stay within the font's limits.
                    pdf.multi_cell(0, 10, pdf_ready_text)
                except:
                    # Fallback for truly "illegal" characters
                    clean_text = pdf_ready_text.encode('ascii', 'ignore').decode('ascii')
                    pdf.multi_cell(0, 10, clean_text)
                
                # Final Byte Conversion
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
