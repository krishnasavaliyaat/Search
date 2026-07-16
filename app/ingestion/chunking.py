def create_paragraph_chunks(book_name: str, ocr_data_list: list) -> list[dict]:
    """
    Flattens paragraph arrays out into individual searchable document records.
    """
    chunks = []
    for page_data in ocr_data_list:
        for para in page_data["paragraphs"]:
            if not para.strip():
                continue
            chunks.append({
                "book_name": book_name,
                "pdf_page_number": page_data["pdf_page_number"],
                "actual_page_defined_in_book": page_data["actual_page_defined_in_book"],
                "text": para.strip(),
                "language": page_data["language"]
            })
    return chunks