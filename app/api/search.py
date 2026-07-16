from fastapi import APIRouter

router = APIRouter(tags=["search"])


@router.get("/search")
def search_documents(query: str) -> dict:
    return {
        "query": query,
        "results": [
            {"title": "Sample document", "content": "Search backend is ready for integration."}
        ],
    }
