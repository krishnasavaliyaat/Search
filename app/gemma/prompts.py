START_DETECTOR_PROMPT = """
Analyze the layout structure of this book page image. 
Your sole task is to determine if this page represents the EXACT first page where the core narrative/content of the book begins.

VISUAL DETECTION RULES FOR BOOK START PAGE:
- CRITICAL SEARCH ANCHOR: The true start page MUST contain BOTH the primary Book Name/Title (in a dominant, extra-large font size) AND the first Main Chapter Heading or initial opening Question centered together directly near the top of the layout structure.
- NEGATIVE BINDING RULES: If the page contains standard layout paragraphs, long narrative text lines, prefaces, standard introduction letters, or biographical summaries, you MUST classify "has_book_started" as false.
- This opening layout page typically does NOT display a physical page index number at the top running margins.

Return the response STRICTLY as a valid JSON object:
{
    "has_book_started": true
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