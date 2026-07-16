import uuid
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, FieldCondition, MatchValue, Filter

class QdrantVectorStore:
    def __init__(self, path: str = "data/qdrant_db"):
        self.client = QdrantClient(path=path)
        self.collection_name = "multilingual_books"
        self._ensure_collection()

    def _ensure_collection(self):
        if not self.client.collection_exists(self.collection_name):
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=1024, distance=Distance.COSINE)
            )

    def delete_book(self, book_name: str):
        """Removes all segments matching the book target to allow clean reprocessing."""
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=Filter(
                must=[FieldCondition(key="book_name", match=MatchValue(value=book_name))]
            )
        )

    def upsert_chunks(self, chunks: list[dict], embedding_engine):
        points = []
        for chunk in chunks:
            vector = embedding_engine.get_embedding(chunk["text"])
            points.append(
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=vector,
                    payload=chunk
                )
            )
        if points:
            self.client.upsert(collection_name=self.collection_name, points=points)

    def search_semantic(self, query_vector: list[float], limit: int = 5):
        return self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=limit
        )