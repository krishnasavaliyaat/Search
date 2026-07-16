import streamlit as st
from pathlib import Path

st.set_page_config(page_title="Ingestion Panel")
st.title("📤 Document Ingest Queue Manager")

uploaded_file = st.file_uploader("Choose a Book PDF", type=["pdf"])
target_folder = st.radio("Target Queue Engine", ["New", "Reprocess"])

if uploaded_file is not None:
    folder_name = "new_pdf" if target_folder == "New" else "reprocess_pdf"
    save_path = Path(__file__).parent.parent / "data" / folder_name / uploaded_file.name
    
    with open(save_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
        
    st.success(f"Successfully dropped file into `{folder_name}/` tracking block.")