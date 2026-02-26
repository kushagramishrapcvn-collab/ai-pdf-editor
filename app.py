import streamlit as st
from google import genai
import fitz  # PyMuPDF
import os

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Symmetry PDF Editor", layout="wide")
st.title("🎯 Layout-Preserving AI Editor")

try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
    client = genai.Client(api_key=API_KEY)
except:
    st.error("Missing API Key in Secrets!")
    st.stop()

# --- 2. THE UI ---
uploaded_file = st.file_uploader("Upload Original PDF", type="pdf")
target_text = st.text_input("Exact text to replace", help="Copy the text from the PDF you want to change")
new_instruction = st.text_area("What should this text become?", placeholder="e.g. 'Correct the calculus error' or 'Translate to English'")

if st.button("Apply Changes & Keep Format"):
    if uploaded_file and target_text:
        with st.spinner("Modifying text layer..."):
            # Save temporary file
            with open("input.pdf", "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            doc = fitz.open("input.pdf")
            found = False

            for page in doc:
                text_instances = page.search_for(target_text)
                
                if text_instances:
                    found = True
                    for inst in text_instances:
                        # 1. Get AI Replacement
                        response = client.models.generate_content(
                            model='gemini-2.5-flash',
                            contents=f"Old text: '{target_text}'. Instruction: {new_instruction}. Return ONLY the replacement text."
                        )
                        replacement = response.text.strip()

                        # 2. STRICT WHITENING: Stays exactly within original bounds
                        page.add_redact_annot(inst, fill=(1, 1, 1)) 
                        page.apply_redactions()

                        # 3. ALIGNED INSERTION: 
                        # We use inst.x0 (left) and inst.y1 (bottom) with a small offset
                        # This 'pushes' the text down into the center of the whitened margin
                        insertion_point = fitz.Point(inst.x0, inst.y1 - 2)

                        page.insert_text(
                            insertion_point, 
                            replacement, 
                            fontsize=10, 
                            fontname="helv", 
                            color=(0, 0, 0)
                        )
            
            if found:
                output_path = "symmetry_fixed.pdf"
                doc.save(output_path)
                with open(output_path, "rb") as f:
                    st.download_button("Download Edited PDF", f, file_name="edited_symmetry.pdf")
            else:
                st.error("Could not find that exact text in the PDF. Please check spelling.")
    else:
        st.warning("Please upload a file and specify the text to replace.")
