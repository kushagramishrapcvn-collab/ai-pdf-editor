import streamlit as st
import fitz  # This is PyMuPDF
from google import genai
import os

# ... (API setup stays the same) ...

if st.button("Edit & Keep Layout"):
    if uploaded_file is not None and user_command:
        # Save the uploaded file temporarily to read it with fitz
        with open("temp.pdf", "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        doc = fitz.open("temp.pdf")
        
        # 1. Ask AI for the change
        # We tell the AI to give us ONLY the specific correction
        full_text = ""
        for page in doc:
            full_text += page.get_text()

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=f"Original Text: {full_text}\nTask: {user_command}\nReturn ONLY the corrected sentence or paragraph. No extra chat."
        )
        new_text = response.text

        # 2. Modify the PDF without changing symmetry
        # Example: Let's assume we are replacing a specific placeholder or the first paragraph
        for page in doc:
            # Search for the text you want to change (you can make this dynamic)
            # For now, let's say we find the specific line the user mentioned
            search_term = st.text_input("Which specific text should I replace?", "Enter old text here")
            
            if search_term:
                areas = page.search_for(search_term)
                for rect in areas:
                    # 'Redact' (erase) the old text area
                    page.add_redact_annot(rect, fill=(1, 1, 1)) # White fill
                    page.apply_redactions()
                    
                    # Insert new text in the exact same box
                    page.insert_text(rect.tl, new_text, fontsize=11, fontname="helv", color=(0,0,0))

        # 3. Save and Download
        doc.save("output.pdf")
        with open("output.pdf", "rb") as f:
            st.download_button("Download Perfect Layout PDF", f, "edited_layout.pdf")
