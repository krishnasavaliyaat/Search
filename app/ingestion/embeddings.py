from sentence_transformers import SentenceTransformer

class EmbeddingEngine:
    def __init__(self):
        # BAAI/bge-m3 handles English, Hinglish, Gujlish alignment mapping natively
        self.model = SentenceTransformer('BAAI/bge-m3')
        
    def get_embedding(self, text: str) -> list[float]:
        return self.model.encode(text).tolist()