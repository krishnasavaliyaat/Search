import json
from PIL import Image
from app.gemma.prompts import OCR_PROMPT

def extract_page_ocr(page, page_num: int, gemma_client_func) -> dict:
    bitmap = page.render(scale=3.0) 
    pil_img = bitmap.to_pil()
    
    response_text = gemma_client_func(pil_img, OCR_PROMPT)
    
    try:
        clean_json = response_text.strip().strip("`").replace("json", "")
        data = json.loads(clean_json)
        return {
            "pdf_page_number": page_num,
            "actual_page_defined_in_book": data.get("actual_page_defined_in_book") or str(page_num),
            "language": data.get("language", "Unknown"),
            "is_main_content": data.get("is_main_content", True),  # Default to True if missing
            "paragraphs": data.get("paragraphs", [])
        }
    except Exception:
        return {
            "pdf_page_number": page_num,
            "actual_page_defined_in_book": str(page_num),
            "language": "Unknown",
            "is_main_content": True,
            "paragraphs": []
        }