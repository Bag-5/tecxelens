from pathlib import Path

from pypdf import PdfReader


def parse_pdf(file_path: str | Path) -> dict:
    path = Path(file_path)
    reader = PdfReader(path)

    text_parts: list[str] = []
    for page in reader.pages:
        extracted = page.extract_text()
        if extracted:
            text_parts.append(extracted)

    return {
        "file_id": path.stem.split("_", 1)[0] if "_" in path.stem else path.stem,
        "text": "\n".join(text_parts),
        "page_count": len(reader.pages),
    }
