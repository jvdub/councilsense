from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from .agenda import extract_agenda_items
from .attachments import extract_attachments
from .metadata import extract_meeting_metadata
from .extract import PdfExtractionError, extract_pdf_text_canonical, normalize_text, read_text_file
from .db import DB_FILENAME, upsert_meeting, upsert_meeting_artifact


class IngestionError(RuntimeError):
    pass


@dataclass(frozen=True)
class ImportedMeeting:
    meeting_id: str
    meeting_dir: Path
    meeting_json_path: Path
    ingestion_json_path: Path


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def generate_meeting_id(pdf_path: Optional[Path], text_path: Optional[Path]) -> str:
    if pdf_path is not None:
        digest = sha256_file(pdf_path)
        return f"pdf_{digest[:12]}"
    if text_path is not None:
        digest = hashlib.sha256(read_text_file(text_path).encode("utf-8")).hexdigest()
        return f"txt_{digest[:12]}"
    # Should never happen; caller validates inputs.
    return f"m_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"


# Backwards-compat alias (internal)
default_meeting_id = generate_meeting_id


def import_meeting(
    *,
    store_dir: Path,
    pdf_path: Optional[Path] = None,
    text_path: Optional[Path] = None,
    meeting_id: Optional[str] = None,
) -> ImportedMeeting:
    if pdf_path is None and text_path is None:
        raise ValueError("pdf_path or text_path is required")

    if meeting_id is None:
        meeting_id = generate_meeting_id(pdf_path, text_path)

    store_dir = store_dir.resolve()
    meeting_dir = (store_dir / meeting_id).resolve()
    meeting_dir.mkdir(parents=True, exist_ok=True)

    imported_at = _utc_now_iso()

    inputs: Dict[str, Any] = {}
    artifacts: Dict[str, Any] = {}
    warnings: list[str] = []

    # I1: stash artifact payloads to mirror into SQLite after upsert_meeting (FK requires meeting row).
    agenda_items_payload_for_db: Optional[list[Dict[str, Any]]] = None
    attachments_payload_for_db: Optional[list[Dict[str, Any]]] = None

    # Track the best available canonical text for downstream artifact generation.
    preferred_text: Optional[Tuple[str, str]] = None  # (source_name, text)

    meeting_date_extracted: Optional[str] = None
    meeting_location_extracted: Optional[str] = None

    if pdf_path is not None:
        pdf_path = pdf_path.resolve()
        if not pdf_path.exists():
            raise IngestionError(f"PDF not found: {pdf_path}")

        pdf_sha = sha256_file(pdf_path)
        pdf_dest = meeting_dir / "source.pdf"
        if not pdf_dest.exists():
            shutil.copy2(pdf_path, pdf_dest)

        try:
            engine, canonical_text = extract_pdf_text_canonical(pdf_dest)
        except PdfExtractionError as e:
            raise IngestionError(str(e)) from e
        text_dest = meeting_dir / "extracted_text.txt"
        text_dest.write_text(canonical_text, encoding="utf-8")

        preferred_text = ("pdf", canonical_text)

        try:
            meeting_date_extracted, meeting_location_extracted = extract_meeting_metadata(canonical_text)
        except Exception:
            pass

        inputs["pdf"] = {
            "original_path": str(pdf_path),
            "stored_path": str(pdf_dest),
            "sha256": pdf_sha,
            "bytes": pdf_dest.stat().st_size,
        }
        artifacts["pdf_text"] = {
            "extractor": engine,
            "stored_path": str(text_dest),
            "chars": len(canonical_text),
            "mode": "canonical",
        }

    if text_path is not None:
        text_path = text_path.resolve()
        if not text_path.exists():
            raise IngestionError(f"Text file not found: {text_path}")

        # Store the original text and a normalized copy (for consistent downstream behavior).
        raw = text_path.read_text(encoding="utf-8", errors="replace")
        raw_dest = meeting_dir / "source.txt"
        if not raw_dest.exists():
            raw_dest.write_text(raw, encoding="utf-8")

        normalized = normalize_text(raw)
        norm_dest = meeting_dir / "extracted_text_from_txt.txt"
        norm_dest.write_text(normalized, encoding="utf-8")

        if preferred_text is None:
            preferred_text = ("text", normalized)

        # Only fill metadata from text if we don't already have it.
        if meeting_date_extracted is None or meeting_location_extracted is None:
            try:
                d, loc = extract_meeting_metadata(normalized)
                if meeting_date_extracted is None:
                    meeting_date_extracted = d
                if meeting_location_extracted is None:
                    meeting_location_extracted = loc
            except Exception:
                pass

        inputs["text"] = {
            "original_path": str(text_path),
            "stored_path": str(raw_dest),
            "sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
            "chars": len(raw),
        }
        artifacts["text_normalized"] = {
            "stored_path": str(norm_dest),
            "chars": len(normalized),
        }

    ingestion = {
        "meeting_id": meeting_id,
        "imported_at": imported_at,
        "inputs": inputs,
        "artifacts": artifacts,
        "warnings": warnings,
    }

    # A3: detect agenda items and store as a separate artifact.
    agenda_items_path = meeting_dir / "agenda_items.json"
    agenda_items_count = 0
    agenda_items_source: Optional[str] = None
    agenda_end = 0
    if preferred_text is not None:
        agenda_items_source, agenda_text = preferred_text
        items = extract_agenda_items(agenda_text)
        agenda_items_count = len(items)
        agenda_end = max((i.end for i in items), default=0)
        agenda_items_payload = [
            {
                "item_id": i.item_id,
                "title": i.title,
                "body_text": i.body_text,
                "start": i.start,
                "end": i.end,
            }
            for i in items
        ]
        agenda_items_payload_for_db = agenda_items_payload
        agenda_items_path.write_text(
            json.dumps(agenda_items_payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        artifacts["agenda_items"] = {
            "stored_path": str(agenda_items_path),
            "count": agenda_items_count,
            "source": agenda_items_source,
            "scan_limit_chars": 200_000,
        }
        if agenda_items_count == 0:
            warnings.append("No agenda items detected; packet may be minutes-only or headings may not match expected patterns.")

    # A4: best-effort attachment/exhibit extraction + type classification.
    attachments_path = meeting_dir / "attachments.json"
    attachments_count = 0
    attachments_source: Optional[str] = None
    if preferred_text is not None:
        attachments_source, attachment_text = preferred_text
        attachments = extract_attachments(attachment_text, agenda_end=agenda_end)
        attachments_count = len(attachments)
        attachments_payload = [
            {
                "attachment_id": a.attachment_id,
                "title": a.title,
                "type_guess": a.type_guess,
                "body_text": a.body_text,
                "start": a.start,
                "end": a.end,
            }
            for a in attachments
        ]
        attachments_payload_for_db = attachments_payload
        attachments_path.write_text(
            json.dumps(attachments_payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        artifacts["attachments"] = {
            "stored_path": str(attachments_path),
            "count": attachments_count,
            "source": attachments_source,
        }

    # Write ingestion.json after all artifacts/warnings are populated.
    ingestion_json_path = meeting_dir / "ingestion.json"
    ingestion_json_path.write_text(
        json.dumps(ingestion, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    meeting = {
        "meeting_id": meeting_id,
        "meeting_date": meeting_date_extracted,
        "meeting_location": meeting_location_extracted,
        "source_files": [
            inputs.get("pdf", {}).get("stored_path"),
            inputs.get("text", {}).get("stored_path"),
        ],
        "extracted_text": {
            "pdf": artifacts.get("pdf_text"),
            "text": artifacts.get("text_normalized"),
        },
        "agenda_items": artifacts.get("agenda_items"),
        "attachments": artifacts.get("attachments"),
        "ingestion_metadata": {
            "imported_at": imported_at,
            "extractor": (artifacts.get("pdf_text") or {}).get("extractor"),
        },
    }

    # Remove nulls for cleanliness
    meeting["source_files"] = [p for p in meeting["source_files"] if p]

    meeting_json_path = meeting_dir / "meeting.json"
    meeting_json_path.write_text(json.dumps(meeting, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # F1: record imported meetings in local SQLite for the meeting list page.
    title: Optional[str] = None
    if isinstance(inputs.get("pdf"), dict):
        orig = inputs["pdf"].get("original_path")
        if orig:
            try:
                title = Path(str(orig)).name
            except Exception:
                title = str(orig)
    if title is None and isinstance(inputs.get("text"), dict):
        orig = inputs["text"].get("original_path")
        if orig:
            try:
                title = Path(str(orig)).name
            except Exception:
                title = str(orig)

    meeting_date: Optional[str] = None
    try:
        # Best-effort: if the meeting_id is an ISO date like YYYY-MM-DD, treat it as the meeting date.
        datetime.strptime(meeting_id, "%Y-%m-%d")
        meeting_date = meeting_id
    except Exception:
        meeting_date = meeting_date_extracted

    meeting_location: Optional[str] = meeting_location_extracted

    upsert_meeting(
        db_path=store_dir / DB_FILENAME,
        meeting_id=meeting_id,
        imported_at=imported_at,
        meeting_dir=meeting_dir,
        meeting_date=meeting_date,
        meeting_location=meeting_location,
        title=title,
        source_pdf_path=(inputs.get("pdf") or {}).get("original_path") if isinstance(inputs.get("pdf"), dict) else None,
        source_text_path=(inputs.get("text") or {}).get("original_path") if isinstance(inputs.get("text"), dict) else None,
    )

    # I1: mirror key import-time artifacts into SQLite.
    if agenda_items_payload_for_db is not None:
        try:
            upsert_meeting_artifact(
                db_path=store_dir / DB_FILENAME,
                meeting_id=meeting_id,
                name="agenda_items",
                obj=agenda_items_payload_for_db,
            )
        except Exception:
            pass

    if attachments_payload_for_db is not None:
        try:
            upsert_meeting_artifact(
                db_path=store_dir / DB_FILENAME,
                meeting_id=meeting_id,
                name="attachments",
                obj=attachments_payload_for_db,
            )
        except Exception:
            pass

    return ImportedMeeting(
        meeting_id=meeting_id,
        meeting_dir=meeting_dir,
        meeting_json_path=meeting_json_path,
        ingestion_json_path=ingestion_json_path,
    )
