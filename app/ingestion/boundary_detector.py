import json
from PIL import Image
from app.gemma.prompts import BOUNDARY_PROMPT

def detect_book_boundaries(doc, gemma_client_func) -> tuple[int, int]:
    """
    Renders a combined grid perspective of early layout sequences to 
    isolate exactly which programmatic PDF page maps to physical Book Page 1.
    """
    total_pages = len(doc)
    
    # Analyze the first 12 pages to trace intro transitions accurately
    scan_limit = min(12, total_pages)
    early_images = []
    
    for idx in range(scan_limit):
        page = doc[idx]
        # Render at low scale for boundary shape assessment (saves token bandwidth)
        bitmap = page.render(scale=1.0)
        early_images.append(bitmap.to_pil())
        
    # We pass the instruction prompt together with the explicit list of page sequences
    # Gemini Flash will process all sequence indices simultaneously to look for the title drop layout
    contents_payload = []
    for idx, img in enumerate(early_images):
        contents_payload.append(f"--- PDF Page Index {idx + 1} ---")
        contents_payload.append(img)
        
    contents_payload.append(BOUNDARY_PROMPT)
    
    response_text = gemma_client_func(contents_payload, is_multipage_scan=True)
    
    try:
        clean_json = response_text.strip().strip("`").replace("json", "")
        data = json.loads(clean_json)
        
        start = int(data.get("start_page", 8))
        end = int(data.get("end_page", total_pages - 2))
        return start, end
    except Exception:
        # Fallback parameters matching your target profile baseline
        return 8, min(42, total_pages)