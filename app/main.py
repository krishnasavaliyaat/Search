from pathlib import Path
from app.ingestion.qdrant_store import QdrantVectorStore
from app.ingestion.embeddings import EmbeddingEngine
from app.ingestion.pdf_processor import execute_pipeline

def main():
    DATA_PATH = Path(__file__).parent.parent / "data"
    store = QdrantVectorStore(path=str(DATA_PATH / "qdrant_db"))
    engine = EmbeddingEngine()
    
    print("Launching ingestion tracking loops...")
    execute_pipeline(DATA_PATH, store, engine)

if __name__ == "__main__":
    main()