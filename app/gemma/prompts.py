START_DETECTOR_PROMPT = """
You are a document layout analyst. Your task is to determine if the provided image is the main title page of a book.

A main title page has these characteristics:
- It features the main title of the book in a large, prominent font.
- It is typically located after front matter like cover pages, publisher logos, or blank pages.
- It should NOT be a table of contents, chapter heading, preface, or index.

Analyze the image and determine if it meets the criteria for a main title page.

Be conservative. If you are not certain, respond with `false`.

Return ONLY a valid JSON object with a single key "is_title_page".

Example:
{
    "is_title_page": true
}
"""

OCR_PROMPT = """
Perform 100% accurate OCR transcription on this book page image with strict structural filtering rules:

1. HEADER REMOVAL RULES:
   - Visually scan the margins, top header bands, and bottom footer zones.
   - Look for recurring layout lines containing running Book Titles or margin number labels.
   - Completely STRIP and REMOVE these headers from your textual output transcriptions.

2. END DETECTION RULES:
   - Analyze if the core body text/narrative has explicitly concluded on this page, shifting into a final book index, publisher advertisement catalogs, back cover elements, or a bibliography. 
   - If the main narrative text has finished, mark "is_core_content_finished" as true.

3. TRANSCRIPTION RULES:
   - Transcribe the core body text exactly as written in its native script (English, Hindi, or Gujarati). Do not clean up grammatical anomalies or translate.
   - Output the text chunks cleanly partitioned into structured paragraph blocks separated by double newlines.
   - Extract the physical page number printed on the page layout as a string, and identify the primary language group ("English", "Hindi", "Gujarati").

Return the response STRICTLY as a valid JSON object:
{
    "actual_page_defined_in_book": "2",
    "language": "Hindi",
    "is_core_content_finished": false,
    "paragraphs": [
        "First paragraph text block exactly as written...",
        "Second paragraph text block exactly as written..."
    ]
}
"""

START_PAGE_PROMPT = """
You are a document layout analyst. Your task is to verify if two sequential image frames represent the start of a book's main content.

- FRAME A: The first image.
- FRAME B: The second image, which immediately follows FRAME A.

Analyze both frames based on these strict rules:

1.  **FRAME A ANALYSIS**:
    - Must be the main title page.
    - It must display the book's primary title in a large, prominent font.
    - It must NOT have a visible page number in its headers or footers.

2.  **FRAME B ANALYSIS**:
    - Must be the second page of the main content.
    - It must have the page number "2" (or its equivalent in another script, like "२") clearly printed in a header or footer.

Return ONLY a valid JSON object indicating if BOTH conditions are met.

Example for a perfect match:
{
    "is_start_sequence": true
}

Example for a non-match:
{
    "is_start_sequence": false
}
"""

END_PAGE_PROMPT = """
You are a document layout analyst. Your task is to determine if the provided image contains a page number.

Page numbers are typically found in the header or footer of a page.
They can be Arabic numerals (1, 2, 3), Roman numerals (i, ii, iii), or numerals from other scripts like Gujarati (૧, ૨, ૩).

Analyze the image and determine if a page number is present. Ignore all other text.

Return ONLY a valid JSON object with two keys:
- "has_page_number": a boolean (true/false).
- "page_number": a string containing the detected page number, or null if not found.

Be precise. If you are not certain, set "has_page_number" to false.

Example for a page with a number:
{
    "has_page_number": true,
    "page_number": "123"
}

Example for a page without a number:
{
    "has_page_number": false,
    "page_number": null
}
"""