import os
import time
import shutil
import json
import pypdfium2 as pdfium
from pathlib import Path
from dotenv import load_dotenv

from app.ingestion.ocr import extract_page_ocr
from app.ingestion.chunking import create_paragraph_chunks
from app.gemma.prompts import START_DETECTOR_PROMPT, OCR_PROMPT

from google import genai
from google.genai import errors, types

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

def call_gemini_flash(image, prompt_text: str) -> str:
    """
    Direct client wrapper to route rapid visual tokens to Gemini Flash.
    """
    try:
        api_key = os.getenv("GEMINI_API_KEY")
        client = genai.Client(api_key=api_key)
        
        response = client.models.generate_content(
            model='gemma-4-31b-it', 
            contents=[image, prompt_text],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1
            )
        )
        return response.text
    except Exception as e:
        print(f"   [API Error] {e}")
        return "{}"

def execute_pipeline(data_dir: Path, db_store, embedding_engine):
    new_dir = data_dir / "new_pdf"
    processed_dir = data_dir / "processed_pdf"
    json_output_dir = data_dir / "json"

    for pdf_path in new_dir.glob("*.pdf"):
        book_name = pdf_path.stem
        print(f"\n[Processing] {pdf_path.name}...")
        
        doc = pdfium.PdfDocument(str(pdf_path))
        ocr_results = []
        
        # State Machine Flags
        has_started = False
        
        try:
            for p_idx in range(len(doc)):
                current_pdf_page = p_idx + 1
                page_layout = doc[p_idx]
                
                # --- STATE 1: SEARCHING FOR CORE CONTENT START ANCHOR ---
                if not has_started:
                    print(f"   -> Scanning PDF Page {current_pdf_page} for book opening anchor...")
                    # --- FIX: Render at scale 2.0 to preserve font size variations for title matching ---
                    layout_res_img = page_layout.render(scale=2.0).to_pil()
                    response_text = call_gemini_flash(layout_res_img, START_DETECTOR_PROMPT)
                    
                    try:
                        data = json.loads(response_text.strip().strip("`").replace("json", ""))
                        if data.get("has_book_started", False):
                            has_started = True
                            print(f"      🎯 [Anchor Found!] Main content identified on PDF Page {current_pdf_page}. Starting OCR workflow.")
                        else:
                            print(f"      [Skipped] Introductory/Editorial layout detected.")
                            time.sleep(1.0)
                            continue
                    except Exception:
                        print(f"      [Skipped] Structural anomaly parsed.")
                        time.sleep(1.0)
                        continue

                # --- STATE 2: ACTIVE HIGH-RESOLUTION OCR ENGINE ---
                # Once has_started turns True, the script skips the detector steps entirely for all subsequent pages
                print(f"   -> Executing High-Precision OCR on PDF Page {current_pdf_page}...")
                high_res_img = page_layout.render(scale=3.0).to_pil()
                response_text = call_gemini_flash(high_res_img, OCR_PROMPT)
                
                try:
                    clean_json = response_text.strip().strip("`").replace("json", "")
                    page_data = json.loads(clean_json)
                    
                    # Package metadata cleanly
                    structured_page = {
                        "pdf_page_number": current_pdf_page,
                        "actual_page_defined_in_book": page_data.get("actual_page_defined_in_book") or str(current_pdf_page),
                        "language": page_data.get("language", "Unknown"),
                        "paragraphs": page_data.get("paragraphs", [])
                    }
                    
                    ocr_results.append(structured_page)
                    print(f"      [Stored] Captured Book Page: {structured_page['actual_page_defined_in_book']}")
                    
                    # --- STATE 3: CORE CONTENT FINISHED ANCHOR ---
                    if page_data.get("is_core_content_finished", False):
                        print(f"      🛑 [End Boundary Detected] AI identified trailing book elements/index. Breaking sequence loop.")
                        break
                        
                except Exception as e:
                    print(f"      [Error] Failed to parse page transcription schema layout: {e}")
                
                time.sleep(1.5) # Gentle rate throttle safety space

            # Save structural JSON backup to disk if we successfully processed text content
            if ocr_results:
                flat_chunks = create_paragraph_chunks(book_name, ocr_results)
                
                json_file = json_output_dir / f"{book_name}.json"
                with open(json_file, "w", encoding="utf-8") as f:
                    json.dump(flat_chunks, f, ensure_ascii=False, indent=4)
                    
                db_store.upsert_chunks(flat_chunks, embedding_engine)
                print(f"-> Vectors and chunks successfully mapped to database coordinates.")
            else:
                print(f"-> [Warning] No narrative pages were captured for this document file.")

        finally:
            doc.close()
        
        shutil.move(str(pdf_path), str(processed_dir / pdf_path.name))
        print(f"-> Successfully completed and relocated: {book_name}\n")