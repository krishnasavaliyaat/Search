import os
from pathlib import Path
from typing import List

from fastapi import APIRouter, File, HTTPException, UploadFile

router = APIRouter(tags=["upload"])

UPLOAD_DIR = Path(__file__).resolve().parents[1] / ".." / "data" / "new_pdf"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/upload")
async def upload_pdf(file: UploadFile = File(...)) -> dict:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Please upload a PDF file")

    destination = UPLOAD_DIR / file.filename
    contents = await file.read()
    destination.write_bytes(contents)
    return {"filename": file.filename, "saved_to": str(destination)}


@router.get("/uploads")
async def list_uploads() -> List[dict]:
    files = []
    for path in sorted(UPLOAD_DIR.glob("*.pdf")):
        files.append({"filename": path.name, "path": str(path)})
    return files
