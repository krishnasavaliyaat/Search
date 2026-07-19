import os
import time
import shutil
import json
import pypdfium2 as pdfium
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv

from app.ingestion.chunking import create_paragraph_chunks
from app.gemma.prompts import START_PAGE_PROMPT, OCR_PROMPT

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

# def find_start_page(doc, book_name: str) -> int:
#     """
#     Finds the true start page by looking for a strict two-page layout signature:
#     - Page A (candidate for page 1) must be the main title page with no page number.
#     - Page B (the next page) must have the printed page number '2'.
#     """
#     total_pages = len(doc)
#     # We subtract 1 because we always need a next page to check
#     max_scan_pages = min(30, total_pages - 1)

#     print(f"🔍 [Locating Content Start] Initiating two-page sequence scan for '{book_name}'...")

#     # We check pairs of pages: (1,2), (2,3), (3,4), etc.
#     for i in range(max_scan_pages):
#         page_a_num = i + 1
#         page_b_num = i + 2
#         print(f"   -> Testing sequence: PDF Page {page_a_num} (as Page 1) & PDF Page {page_b_num} (as Page 2)...")

#         # Render both candidate pages
#         img_a = doc[i].render(scale=2.0).to_pil()
#         img_b = doc[i+1].render(scale=2.0).to_pil()

#         try:
#             # Package frames for the multimodal prompt
#             payload = [
#                 "--- FRAME A ---", img_a,
#                 "--- FRAME B ---", img_b,
#                 START_PAGE_PROMPT
#             ]
#             response_text = call_gemma_api(payload)
#             time.sleep(3)  # API cooldown

#             clean_json = response_text.strip().strip("`").replace("json", "")
#             data = json.loads(clean_json)

#             if data.get("is_start_sequence", False):
#                 print(f"      🎯 [Sequence Verified!] PDF Page {page_a_num} locked as true start page.")
#                 return page_a_num

#         except Exception as e:
#             print(f"      [Warning] Anomaly on sequence check for pages {page_a_num}-{page_b_num}: {e}")
#             continue

#     print("⚠️ [Search Complete] Two-page verification inconclusive. Defaulting to PDF Page 1.")
#     return 1

def find_start_page(doc, book_name: str) -> int:
    """
    Finds the start page by locating the first printed page number '2'.
    The start page is assumed to be the previous PDF page.
    """
    total_pages = len(doc)

    print(f"🔍 [Locating Content Start] Scanning '{book_name}'...")

    for pdf_page in range(3, total_pages + 1):
        print(f"   -> Checking PDF Page {pdf_page}")

        image = doc[pdf_page - 1].render(scale=2.0).to_pil()

        try:
            response_text = call_gemma_api([image, START_PAGE_PROMPT])
            time.sleep(3)

            clean_json = response_text.strip().strip("`").replace("json", "")
            data = json.loads(clean_json)

            if data.get("has_page_2", False):
                start_page = max(1, pdf_page - 1)

                print(
                    f"      🎯 Printed page number '2' found on PDF Page {pdf_page}. "
                    f"Start page = PDF Page {start_page}"
                )

                return start_page

        except Exception as e:
            print(f"      [Warning] Error on PDF Page {pdf_page}: {e}")

    print("⚠️ Printed page number '2' not found. Defaulting to PDF Page 1.")
    return 1

def execute_pipeline(data_dir: Path, db_store, embedding_engine, book_to_process: str = None):
    """
    Executes the OCR and ingestion pipeline for books with pre-defined boundaries.
    If `book_to_process` is specified, it only processes that single book.
    Otherwise, it processes all books found in the boundary file that haven't been processed.
    """
    boundary_file = Path(__file__).parent / "boundaries.xlsx"
    processed_dir = data_dir / "processed_pdf"
    source_dir = data_dir / "new_pdf"
    json_output_dir = data_dir / "json"
        
    if not boundary_file.exists():
        print(f"Error: Boundary file not found at '{boundary_file}'.")
        print("Please run `find_boundaries.py` first to generate it.")
        return

    boundary_df = pd.read_excel(boundary_file)

    if book_to_process:
        boundary_df = boundary_df[boundary_df["book_name"] == book_to_process]

    for _, row in boundary_df.iterrows():
        book_name = row["book_name"]
        start_pdf_page = int(row["start_page"])
        end_pdf_page = int(row["end_page"])

        language = row["language"]
        pdf_path = source_dir / language / book_name
        if not pdf_path.exists():
            print(f"Skipping '{book_name}': PDF file not found in '{source_dir}'. It may have been processed already.")
            continue

        print(f"\n[Processing OCR] {book_name} from page {start_pdf_page} to {end_pdf_page}...")
        doc = pdfium.PdfDocument(str(pdf_path))
        ocr_results = []
        

        try:
            # The start page is now read from the boundary file.
            for current_pdf_page in range(start_pdf_page, end_pdf_page + 1):
                p_idx = current_pdf_page - 1
                page_layout = doc[p_idx]
                
                page_success = False
                max_ocr_retries = 5
                end_boundary_detected = False
                
                # --- 5-ATTEMPT RETRY ENGINE FOR ACCURATE CONTENT MATCHING ---
                for attempt in range(1, max_ocr_retries + 1):
                    try:
                        print(f"   -> Executing High-Precision OCR on PDF Page {current_pdf_page} (Attempt {attempt}/{max_ocr_retries})...")
                        high_res_img = page_layout.render(scale=3.0).to_pil() # TODO: This is not being passed to call_gemma_api
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
                flat_chunks = create_paragraph_chunks(pdf_path.stem, ocr_results)
                
                json_file = json_output_dir / f"{book_name}.json"
                json_file = json_output_dir / f"{pdf_path.stem}.json"
                with open(json_file, "w", encoding="utf-8") as f:
                    json.dump(flat_chunks, f, ensure_ascii=False, indent=4)
                    
                db_store.upsert_chunks(flat_chunks, embedding_engine)
                print(f"-> Vectors and chunks successfully mapped to database coordinates.")
            else:
                print(f"-> [Warning] No narrative pages were captured for this document file.")
                print(f"-> [Warning] No narrative pages were captured for {book_name}.")

        finally:
            doc.close()
        
        shutil.move(str(pdf_path), str(processed_dir / pdf_path.name))
        shutil.move(str(pdf_path), str(processed_dir / book_name))
        print(f"-> Successfully completed and relocated: {book_name}\n")