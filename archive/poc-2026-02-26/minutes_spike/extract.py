from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class PdfExtractionError(RuntimeError):
    pass


def normalize_text(text: str) -> str:
    # Keep ordering stable; normalize common PDF/text artifacts.
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\u00a0", " ")  # NBSP
    text = text.replace("\u200b", "")  # zero-width space
    text = text.replace("\t", " ")

    # Clean per-line to reduce extractor jitter while preserving line boundaries.
    lines: List[str] = []
    for line in text.split("\n"):
        line = line.rstrip()
        # Collapse repeated spaces in the non-indentation portion.
        m = re.match(r"^ *", line)
        indent = m.group(0) if m else ""
        rest = line[len(indent) :]
        rest = re.sub(r" {2,}", " ", rest)
        lines.append(indent + rest)

    text = "\n".join(lines)

    # Collapse excessive blank lines.
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def read_text_file(path: Path) -> str:
    return normalize_text(path.read_text(encoding="utf-8", errors="replace"))


def extract_pdf_text_pymupdf(path: Path) -> Optional[str]:
    try:
        import fitz  # PyMuPDF
    except Exception:
        return None

    doc = fitz.open(str(path))
    try:
        parts: List[str] = []
        for page in doc:
            parts.append(page.get_text("text"))
        return normalize_text("\n".join(parts))
    finally:
        doc.close()


def extract_pdf_text_pdfplumber(path: Path) -> Optional[str]:
    try:
        import pdfplumber
    except Exception:
        return None

    parts: List[str] = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            parts.append(page.extract_text() or "")

    joined = "\n".join(parts).strip()
    if not joined:
        return None
    return normalize_text(joined)


def extract_pdf_text_pypdf(path: Path) -> Optional[str]:
    try:
        from pypdf import PdfReader
    except Exception:
        return None

    reader = PdfReader(str(path))
    parts: List[str] = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            parts.append("")

    joined = "\n".join(parts).strip()
    if not joined:
        return None
    return normalize_text(joined)


def extract_pdf_text_all(path: Path) -> Dict[str, Optional[str]]:
    return {
        "pymupdf": extract_pdf_text_pymupdf(path),
        "pdfplumber": extract_pdf_text_pdfplumber(path),
        "pypdf": extract_pdf_text_pypdf(path),
    }


def extract_pdf_text_canonical(path: Path) -> Tuple[str, str]:
    """Extract text from a PDF using the single canonical extractor.

    A2 requirement: extracted text should be stable across runs. We therefore
    pick one primary extractor (PyMuPDF) and do not mix outputs.
    """

    try:
        import fitz  # PyMuPDF
    except Exception as e:
        raise PdfExtractionError(
            "PyMuPDF is required for PDF extraction (pip install PyMuPDF)."
        ) from e

    try:
        doc = fitz.open(str(path))
    except Exception as e:
        raise PdfExtractionError(f"Failed to open PDF: {path}") from e

    try:
        parts: List[str] = []
        for idx, page in enumerate(doc, start=1):
            try:
                parts.append(page.get_text("text") or "")
            except Exception as e:
                raise PdfExtractionError(f"Failed to extract text from page {idx}.") from e
    finally:
        doc.close()

    text = normalize_text("\n".join(parts))
    if not text.strip():
        raise PdfExtractionError(
            "PDF appears scanned or has no extractable text; OCR is not supported yet."
        )

    return "pymupdf", text
