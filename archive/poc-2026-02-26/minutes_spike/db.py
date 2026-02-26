from __future__ import annotations

import sqlite3
from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import json
from datetime import datetime, timezone


DB_FILENAME = "meetings.sqlite3"


@dataclass(frozen=True)
class MeetingRow:
    meeting_id: str
    imported_at: str
    meeting_date: Optional[str]
    meeting_location: Optional[str]
    title: Optional[str]
    meeting_dir: str
    source_pdf_path: Optional[str]
    source_text_path: Optional[str]


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: Path) -> None:
    with _connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS meetings (
                meeting_id TEXT PRIMARY KEY,
                imported_at TEXT NOT NULL,
                meeting_date TEXT,
                meeting_location TEXT,
                title TEXT,
                meeting_dir TEXT NOT NULL,
                source_pdf_path TEXT,
                source_text_path TEXT
            );

            CREATE TABLE IF NOT EXISTS meeting_artifacts (
                meeting_id TEXT NOT NULL,
                name TEXT NOT NULL,
                json TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (meeting_id, name),
                FOREIGN KEY (meeting_id) REFERENCES meetings(meeting_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS llm_cache (
                cache_key TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                model_provider TEXT,
                model_endpoint TEXT,
                model TEXT,
                prompt_id TEXT,
                prompt_version INTEGER
            );

            CREATE INDEX IF NOT EXISTS idx_meetings_imported_at ON meetings(imported_at);
            CREATE INDEX IF NOT EXISTS idx_artifacts_meeting ON meeting_artifacts(meeting_id);
            CREATE INDEX IF NOT EXISTS idx_artifacts_name ON meeting_artifacts(name);
            CREATE INDEX IF NOT EXISTS idx_llm_cache_kind ON llm_cache(kind);
            """
        )

        # Best-effort migration for existing DBs.
        try:
            cols = {str(r[1]) for r in conn.execute("PRAGMA table_info(meetings)").fetchall()}
        except Exception:
            cols = set()

        if "meeting_location" not in cols:
            try:
                conn.execute("ALTER TABLE meetings ADD COLUMN meeting_location TEXT")
            except Exception:
                pass


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def stable_hash_json(obj: object) -> str:
    """Compute a stable sha256 of a JSON-serializable object."""
    payload = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def upsert_meeting_artifact(*, db_path: Path, meeting_id: str, name: str, obj: object) -> None:
    """Store a JSON-serializable artifact for a meeting.

    This mirrors data that also exists on disk in the meeting folder.
    """

    init_db(db_path)
    payload = json.dumps(obj, ensure_ascii=False)
    updated_at = _utc_now_iso()
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO meeting_artifacts (meeting_id, name, json, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(meeting_id, name) DO UPDATE SET
                json=excluded.json,
                updated_at=excluded.updated_at
            """,
            (meeting_id, str(name), payload, updated_at),
        )


def get_meeting_artifact(*, db_path: Path, meeting_id: str, name: str) -> Optional[object]:
    init_db(db_path)
    with _connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT json
            FROM meeting_artifacts
            WHERE meeting_id = ? AND name = ?
            """,
            (meeting_id, str(name)),
        ).fetchone()
    if row is None:
        return None
    try:
        return json.loads(str(row["json"]))
    except Exception:
        return None


def meeting_artifact_exists(*, db_path: Path, meeting_id: str, name: str) -> bool:
    init_db(db_path)
    with _connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT 1
            FROM meeting_artifacts
            WHERE meeting_id = ? AND name = ?
            LIMIT 1
            """,
            (meeting_id, str(name)),
        ).fetchone()
    return row is not None


def list_meeting_artifact_names(*, db_path: Path, meeting_id: str) -> List[str]:
    init_db(db_path)
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT name
            FROM meeting_artifacts
            WHERE meeting_id = ?
            ORDER BY name
            """,
            (meeting_id,),
        ).fetchall()
    return [str(r["name"]) for r in rows]


def get_llm_cache(*, db_path: Path, cache_key: str) -> Optional[object]:
    init_db(db_path)
    with _connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT json
            FROM llm_cache
            WHERE cache_key = ?
            """,
            (str(cache_key),),
        ).fetchone()
    if row is None:
        return None
    try:
        return json.loads(str(row["json"]))
    except Exception:
        return None


def put_llm_cache(
    *,
    db_path: Path,
    cache_key: str,
    kind: str,
    obj: object,
    model_provider: Optional[str] = None,
    model_endpoint: Optional[str] = None,
    model: Optional[str] = None,
    prompt_id: Optional[str] = None,
    prompt_version: Optional[int] = None,
) -> None:
    init_db(db_path)
    payload = json.dumps(obj, ensure_ascii=False)
    created_at = _utc_now_iso()
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO llm_cache (
                cache_key, kind, json, created_at, model_provider, model_endpoint, model, prompt_id, prompt_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(cache_key) DO UPDATE SET
                json=excluded.json,
                created_at=excluded.created_at,
                kind=excluded.kind,
                model_provider=excluded.model_provider,
                model_endpoint=excluded.model_endpoint,
                model=excluded.model,
                prompt_id=excluded.prompt_id,
                prompt_version=excluded.prompt_version
            """,
            (
                str(cache_key),
                str(kind),
                payload,
                created_at,
                model_provider,
                model_endpoint,
                model,
                prompt_id,
                int(prompt_version) if prompt_version is not None else None,
            ),
        )


def upsert_meeting(
    *,
    db_path: Path,
    meeting_id: str,
    imported_at: str,
    meeting_dir: Path,
    meeting_date: Optional[str] = None,
    meeting_location: Optional[str] = None,
    title: Optional[str] = None,
    source_pdf_path: Optional[str] = None,
    source_text_path: Optional[str] = None,
) -> None:
    init_db(db_path)
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO meetings (
                meeting_id, imported_at, meeting_date, meeting_location, title, meeting_dir, source_pdf_path, source_text_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(meeting_id) DO UPDATE SET
                imported_at=excluded.imported_at,
                meeting_date=COALESCE(excluded.meeting_date, meetings.meeting_date),
                meeting_location=COALESCE(excluded.meeting_location, meetings.meeting_location),
                title=COALESCE(excluded.title, meetings.title),
                meeting_dir=excluded.meeting_dir,
                source_pdf_path=COALESCE(excluded.source_pdf_path, meetings.source_pdf_path),
                source_text_path=COALESCE(excluded.source_text_path, meetings.source_text_path)
            """,
            (
                meeting_id,
                imported_at,
                meeting_date,
                meeting_location,
                title,
                str(meeting_dir),
                source_pdf_path,
                source_text_path,
            ),
        )


def list_meetings(*, db_path: Path, limit: int = 200) -> List[MeetingRow]:
    init_db(db_path)
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT meeting_id, imported_at, meeting_date, meeting_location, title, meeting_dir, source_pdf_path, source_text_path
            FROM meetings
            ORDER BY imported_at DESC
            LIMIT ?
            """,
            (int(limit),),
        ).fetchall()

    out: List[MeetingRow] = []
    for r in rows:
        out.append(
            MeetingRow(
                meeting_id=str(r["meeting_id"]),
                imported_at=str(r["imported_at"]),
                meeting_date=(str(r["meeting_date"]) if r["meeting_date"] is not None else None),
                meeting_location=(str(r["meeting_location"]) if r["meeting_location"] is not None else None),
                title=(str(r["title"]) if r["title"] is not None else None),
                meeting_dir=str(r["meeting_dir"]),
                source_pdf_path=(str(r["source_pdf_path"]) if r["source_pdf_path"] is not None else None),
                source_text_path=(str(r["source_text_path"]) if r["source_text_path"] is not None else None),
            )
        )
    return out


def get_meeting(*, db_path: Path, meeting_id: str) -> Optional[MeetingRow]:
    init_db(db_path)
    with _connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT meeting_id, imported_at, meeting_date, meeting_location, title, meeting_dir, source_pdf_path, source_text_path
            FROM meetings
            WHERE meeting_id = ?
            """,
            (meeting_id,),
        ).fetchone()

    if row is None:
        return None

    return MeetingRow(
        meeting_id=str(row["meeting_id"]),
        imported_at=str(row["imported_at"]),
        meeting_date=(str(row["meeting_date"]) if row["meeting_date"] is not None else None),
        meeting_location=(str(row["meeting_location"]) if row["meeting_location"] is not None else None),
        title=(str(row["title"]) if row["title"] is not None else None),
        meeting_dir=str(row["meeting_dir"]),
        source_pdf_path=(str(row["source_pdf_path"]) if row["source_pdf_path"] is not None else None),
        source_text_path=(str(row["source_text_path"]) if row["source_text_path"] is not None else None),
    )
