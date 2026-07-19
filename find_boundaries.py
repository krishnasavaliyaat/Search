import os
import time
import json
from pathlib import Path

import pandas as pd
import pypdfium2 as pdfium
from dotenv import load_dotenv

from app.gemma.prompts import END_PAGE_PROMPT
from app.ingestion.pdf_processor import call_gemma_api, find_start_page

load_dotenv()

DATA_PATH = Path(__file__).parent / "data"
PDF_SOURCE_DIR = DATA_PATH / "new_pdf"
BOUNDARY_FILE = Path(__file__).parent / "boundaries.xlsx"


def find_end_page(doc) -> int:
    """
    Finds the last page of the core content by iterating backwards from the end
    and looking for the last page that contains a page number.
    """
    total_pages = len(doc)

    # Skip last two pages
    start_scan = max(total_pages - 2, 1)
    print("🔍 [Locating Content End] Initiating reverse scan for last numbered page...")


    for i in range(start_scan, 0, -1):
        page_idx = i - 1
        print(f"   -> Checking for page number on PDF Page {i}...")

        try:
            page = doc[page_idx]
            # Low DPI is fine for just finding a page number
            image = page.render(scale=1.5).to_pil()

            # The prompt now expects a single image, not a list
            response_text = call_gemma_api([image, END_PAGE_PROMPT])
            time.sleep(2)  # API cooldown

            clean_json = response_text.strip().strip("`").replace("json", "")
            data = json.loads(clean_json)

            if data.get("has_page_number"):
                page_num_str = data.get('page_number', 'N/A')
                print(f"      🎯 [End Boundary Found] Last numbered page is PDF Page {i} (Detected number: '{page_num_str}').")
                return i

        except Exception as e:
            print(f"      [Warning] Anomaly on end-page check for page {i}: {e}")
            continue

    print(f"⚠️ [Search Complete] End page detection inconclusive. Defaulting to last page: {total_pages}.")
    return total_pages

def save_boundaries_to_excel(df: pd.DataFrame):
    """Saves the DataFrame to the Excel file."""
    try:
        df.to_excel(BOUNDARY_FILE, index=False)
        print(f"💾 Boundary file '{BOUNDARY_FILE}' saved.")
    except Exception as e:
        print(f"❌ Error saving boundary file: {e}")


def main():
    """
    Main function to find start/end boundaries for all PDFs and save to Excel.
    """
    pdf_files = list(PDF_SOURCE_DIR.rglob("*.pdf"))
    if not pdf_files:
        print("No new PDFs found in `data/new_pdf` to process.")
        return

    if BOUNDARY_FILE.exists():
        try:
            existing_df = pd.read_excel(BOUNDARY_FILE)
            print(f"Loaded {len(existing_df)} existing records from {BOUNDARY_FILE}.")
        except Exception as e:
            print(f"Could not read existing boundary file, creating a new one. Error: {e}")
            existing_df = pd.DataFrame(columns=["book_name","language","start_page","end_page",])
    else:
        existing_df = pd.DataFrame(columns=["book_name","language","start_page","end_page",])


    # Ensure book_name is string type for merging
    existing_df['book_name'] = existing_df['book_name'].astype(str)

    new_records = []

    for pdf_path in pdf_files:
        book_name = pdf_path.name
        language = pdf_path.parent.name
        mask = ((existing_df["book_name"] == book_name) &(existing_df["language"] == language))

        if mask.any():
            row = existing_df.loc[mask].iloc[0]

            start_page = row["start_page"]
            end_page = row["end_page"]

            # Skip only if both boundaries already exist
            if pd.notna(start_page) and pd.notna(end_page):
                print(f"Skipping '{language}/{book_name}', boundaries already complete.")
                continue

            # Resume from end-page detection
            resume_end_only = True
            print(f"Resuming '{language}/{book_name}' (start page already found).")

        else:
            resume_end_only = False

        print("\n======================================")
        print(f"Processing: {book_name}")
        print("======================================")

        try:
            doc = pdfium.PdfDocument(str(pdf_path))
            
            # 1. Find and save start page first
            if not resume_end_only:
                start_page = find_start_page(doc, pdf_path.stem)

                temp_record = {
                    "book_name": book_name,
                    "language": language,
                    "start_page": start_page,
                    "end_page": "",
                }

                new_records.append(temp_record)

                updated_df = pd.concat(
                    [existing_df, pd.DataFrame(new_records)],
                    ignore_index=True
                )
                save_boundaries_to_excel(updated_df)

            else:
                start_page = int(start_page)

            print(f"   -> Start Page: {start_page} (Saved progress)")

            # 2. Find end page
            end_page = find_end_page(doc)

            # 3. Update the record with the end page
            # Find the record we just added and update its end_page
            if resume_end_only:
                idx = existing_df.index[mask][0]

                existing_df.at[idx, "end_page"] = end_page

                save_boundaries_to_excel(existing_df)

            else:
                for record in new_records:
                    if (
                        record["book_name"] == book_name
                        and record["language"] == language
                    ):
                        record["end_page"] = end_page
                        break
            
            print(f"✅ Completed boundary detection for: {book_name}")
            print(f"   -> Final Boundaries -> Start: {start_page}, End: {end_page}")

        except Exception as e:
            print(f"❌ Critical error processing {book_name}: {e}")
        finally:
            if 'doc' in locals() and doc:
                doc.close()
    
    if new_records: # Save the final complete data
        print(new_records)
        print(pd.DataFrame(new_records))
        final_df = pd.concat([existing_df, pd.DataFrame(new_records)], ignore_index=True)
        save_boundaries_to_excel(final_df)
        print(f"\nBoundary file update process complete for {len(new_records)} new entries.")

if __name__ == "__main__":
    main()
