import os
import time
import shutil
import json
import pypdfium2 as pdfium
from pathlib import Path
from dotenv import load_dotenv

from app.ingestion.chunking import create_paragraph_chunks
from app.gemma.prompts import START_DETECTOR_PROMPT, OCR_PROMPT

from google import genai
from google.genai import errors, types

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

def call_gemma_api(payload_data, is_multipage_scan: bool = False) -> str:
    """
    Executes live multimodal inference using Gemma-4/Gemini with quota handling.
    Accepts both standard [image, prompt] inputs and multipage grid arrays.
    """
    while True:
        try:
            api_key = os.getenv("GEMINI_API_KEY")
            client = genai.Client(api_key=api_key)

            # If payload_data is already packaged as an array (multipage scan), 
            # we pass it directly. Otherwise, it handles standard single page requests.
            contents = payload_data

            response = client.models.generate_content(
                model='gemma-4-31b-it',  
                contents=contents,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1
                )
            )
            return response.text
        except errors.APIError as e:
            if e.code == 429 or e.code == 503:
                print("   ⚠️ [Quota Limit Hit] Input tokens per minute exhausted. Sleeping for 20 seconds...")
                time.sleep(20)
                continue
            raise e
        except Exception as e:
            print(f"   [API Error] {e}")
            return "{}"

def find_start_page_binary(doc) -> int:
    """
    Finds the true Book Page 1 by looking for a strict two-page layout signature:
    - Page A must contain the Main Book Title and primary Chapter Heading near the top.
    - Page B (the immediate next page) must have the printed page number '2' in its header.
    """
    total_pages = len(doc)
    # Scan early pages where the start block could realistically be located
    max_scan_pages = min(60, total_pages - 1) 

    print("🔍 [Locating Content Start] Initiating strict two-page sequential verification...")

    for current_page in range(1, max_scan_pages + 1):
        print(f"   -> Testing sequence: PDF Page {current_page} (as Page 1) & PDF Page {current_page + 1} (as Page 2)...")

        # 1. Render both candidate pages
        img_a = doc[current_page - 1].render(scale=2.5).to_pil()
        img_b = doc[current_page].render(scale=2.5).to_pil()

        # 2. Package both frames together into a single contents list
        payload = [
            "--- FRAME A (Candidate Page 1) ---",
            img_a,
            "--- FRAME B (Candidate Page 2) ---",
            img_b,
            START_DETECTOR_PROMPT
        ]

        # Call the updated function definition safely
        response_text = call_gemma_api(payload, is_multipage_scan=True)

        # Safe cooldown delay to manage token-per-minute limits
        time.sleep(3)

        try:
            clean_json = response_text.strip().strip("`").replace("json", "")
            data = json.loads(clean_json)

            # Both conditions must be marked true by the model
            if data.get("is_frame_a_title_page", False) and data.get("is_frame_b_page_two", False):
                print(f"      🎯 [Sequence Verified!] PDF Page {current_page} locked as true start page.")
                return current_page

        except Exception as e:
            print(f"      [Warning] Parsing anomaly on sequence check {current_page}: {e}")
            continue

    print("⚠️ [Search Complete] Two-page verification inconclusive. Defaulting safely to PDF Page 1.")
    return 1

def execute_pipeline(data_dir: Path, db_store, embedding_engine):
    new_dir = data_dir / "new_pdf"
    processed_dir = data_dir / "processed_pdf"
    json_output_dir = data_dir / "json"

    for pdf_path in new_dir.glob("*.pdf"):
        book_name = pdf_path.stem
        print(f"\n[Processing] {pdf_path.name}...")
        
        doc = pdfium.PdfDocument(str(pdf_path))
        ocr_results = []
        
        try:
            # Step 1: Discover structural starting anchor accurately via dynamic scanning bounds
            start_pdf_page = find_start_page_binary(doc)
            print(f"-> Starting high-precision transcription processing from PDF Page {start_pdf_page}...")

            # Step 2: Loop linearly out from the isolated start page coordinate
            for current_pdf_page in range(start_pdf_page, len(doc) + 1):
                p_idx = current_pdf_page - 1
                page_layout = doc[p_idx]
                
                page_success = False
                max_ocr_retries = 5
                end_boundary_detected = False
                
                # --- 5-ATTEMPT RETRY ENGINE FOR ACCURATE CONTENT MATCHING ---
                for attempt in range(1, max_ocr_retries + 1):
                    try:
                        print(f"   -> Executing High-Precision OCR on PDF Page {current_pdf_page} (Attempt {attempt}/{max_ocr_retries})...")
                        high_res_img = page_layout.render(scale=3.0).to_pil()
                        response_text = call_gemma_api(high_res_img, OCR_PROMPT)
                        
                        clean_json = response_text.strip().strip("`").replace("json", "")
                        parsed_data = json.loads(clean_json)
                        
                        # --- STRUCTURAL NORMALIZATION GUARD ---
                        # If the output parsed as a list array instead of a root dictionary object,
                        # safely extract the first element block or normalize the key structure.
                        if isinstance(parsed_data, list):
                            if len(parsed_data) > 0 and isinstance(parsed_data[0], dict):
                                page_data = parsed_data[0]
                            else:
                                # Fallback object map if the list is flat strings or empty
                                page_data = {
                                    "actual_page_defined_in_book": str(current_pdf_page),
                                    "language": "Unknown",
                                    "is_core_content_finished": False,
                                    "paragraphs": [str(item) for item in parsed_data] if parsed_data else []
                                }
                        else:
                            page_data = parsed_data
                        
                        # Inspect structural tracking flag to detect ending book parameters
                        if page_data.get("is_core_content_finished", False):
                            print(f"      🛑 [End Boundary Detected] AI identified trailing book indexes/back cover elements.")
                            end_boundary_detected = True
                            page_success = True
                            break
                            
                        structured_page = {
                            "pdf_page_number": current_pdf_page,
                            "actual_page_defined_in_book": page_data.get("actual_page_defined_in_book") or str(current_pdf_page),
                            "language": page_data.get("language", "Unknown"),
                            "paragraphs": page_data.get("paragraphs", [])
                        }
                        
                        ocr_results.append(structured_page)
                        print(f"      [Stored] Captured Book Page: {structured_page['actual_page_defined_in_book']}")
                        
                        page_success = True
                        break  # Page execution succeeded, break out of retry loop
                        
                    except Exception as e:
                        print(f"      ⚠️ [Attempt {attempt} Failed] Parsing anomaly or API glitch: {e}")
                        if attempt < max_ocr_retries:
                            print("         Sleeping for 10 seconds before attempting recalculation...")
                            time.sleep(10)
                        else:
                            print(f"      ❌ [Critical Error] Page {current_pdf_page} failed processing limits completely.")
                
                # Structural circuit breaker: Halt sequence if validation engine completely drops a page
                if not page_success:
                    raise RuntimeError(f"Pipeline Execution Aborted: PDF Page {current_pdf_page} failed parsing completely after {max_ocr_retries} attempts.")
                
                # If trailing elements were verified inside the retry block, drop processing loops cleanly
                if end_boundary_detected:
                    print("Breaking sequence loop.")
                    break
                
                # --- TOKENS PER MINUTE SAFETY SLEEP ---
                # A 5-second sleep ensures your token balance stays within the 16,000 limit
                time.sleep(5)

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