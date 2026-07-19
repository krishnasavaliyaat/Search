START_DETECTOR_PROMPT = """
Analyze the layout structure of both image frames simultaneously to verify if they match the strict starting layout sequence of a book:

1. EVALUATE FRAME A (Candidate Page 1):
   - Check if this frame marks the first page of the core content. 
   - VISUAL SIGNATURE: It must display the primary Book Title/Name prominently in a large font size near the upper-middle section, with the first Main Chapter Heading or Question positioned directly beneath it[cite: 2].
   - There should be NO running page number labels printed in the top margins[cite: 2].
   - If this matches, set "is_title_heading_present" to true.

2. EVALUATE FRAME B (Candidate Page 2):
   - Check the running margins, top header bands, and bottom footer zones.
   - VISUAL SIGNATURE: It must explicitly show the physical layout page number "2" (or "२" in native scripts) printed in the margin zone[cite: 2].
   - If this matches, set "is_page_two_present" to true.

Return the response STRICTLY as a valid JSON object:
{
    "is_frame_a_title_page": true,
    "is_frame_b_page_two": true
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