import base64
import io
from typing import Tuple
from pypdf import PdfReader


def extract_pdf_data(file_bytes: bytes) -> Tuple[str, str]:
    """
    Retorna (base64_str, extracted_text) a partir dos bytes de um arquivo PDF.
    O base64_str é enviado nativamente para o Gemini Interactions API (type='document'),
    enquanto extracted_text serve como backup e indexação local.
    """
    b64_data = base64.b64encode(file_bytes).decode("utf-8")
    text_parts = []
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        for page in reader.pages:
            page_text = page.extract_text() or ""
            if page_text.strip():
                text_parts.append(page_text.strip())
    except Exception:
        pass
    return b64_data, "\n\n".join(text_parts)
