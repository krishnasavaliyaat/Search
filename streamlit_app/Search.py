import streamlit as st
from pathlib import Path
from app.ingestion.qdrant_store import QdrantVectorStore
from app.ingestion.embeddings import EmbeddingEngine

st.set_page_config(page_title="Semantic Search Console", layout="wide")
st.title("🔍 Multi-script Cross Language Search")

@st.cache_resource
def init_search_resources():
    db_path = str(Path(__file__).parent.parent / "data" / "qdrant_db")
    return QdrantVectorStore(path=db_path), EmbeddingEngine()

store, engine = init_search_resources()

query = st.text_input("Search context (Phonetic scripts supported, e.g. 'Chinta etle shu?')")

if query:
    with st.spinner("Decoding language vectors..."):
        v_query = engine.get_embedding(query)
        hits = store.search_semantic(v_query, limit=5)
        
        if not hits:
            st.warning("No context fragments matched this vector index.")
            
        for hit in hits:
            p = hit.payload
            with st.expander(f"📖 {p['book_name']} — Page {p['actual_page_defined_in_book']} (Score: {hit.score:.3f})"):
                st.caption(f"Language Category: {p['language']} | PDF Sequence Position: {p['pdf_page_number']}")
                st.write(p['text'])