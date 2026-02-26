from __future__ import annotations

import hashlib
import http.client
import json
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from minutes_spike.web import _Handler, sync_store_dir_to_db


def _multipart_body(*, boundary: str, parts: list[tuple[str, str, str, bytes]]) -> bytes:
    # parts: (field_name, filename, content_type, bytes)
    chunks: list[bytes] = []
    for field, filename, content_type, data in parts:
        chunks.append(f"--{boundary}\r\n".encode("utf-8"))
        chunks.append(
            (
                f'Content-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'
                f"Content-Type: {content_type}\r\n\r\n"
            ).encode("utf-8")
        )
        chunks.append(data)
        chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(chunks)


def _start_server(*, store_dir: Path) -> tuple[ThreadingHTTPServer, int, threading.Thread]:
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    httpd.store_dir = store_dir  # type: ignore[attr-defined]

    sync_store_dir_to_db(store_dir=store_dir)

    t = threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    t.start()
    return httpd, int(httpd.server_address[1]), t


def test_k2_api_import_list_and_detail(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "minutes_spike.store.extract_pdf_text_canonical",
        lambda _path: (
            "pymupdf",
            "CITY COUNCIL REGULAR MEETING\nJanuary 23, 2026\nLocation: City Hall Council Chambers\n\n1. CALL TO ORDER\nHello\n\n2.A. ORDINANCE - CODE UPDATE\nAn ordinance...\n",
        ),
    )

    store_dir = tmp_path / "store"
    store_dir.mkdir(parents=True, exist_ok=True)

    httpd, port, t = _start_server(store_dir=store_dir)

    try:
        boundary = "----councilsense-test-boundary"
        pdf_bytes = b"%PDF-1.4\n%fake\n"
        expected_meeting_id = f"pdf_{hashlib.sha256(pdf_bytes).hexdigest()[:12]}"

        body = _multipart_body(
            boundary=boundary,
            parts=[
                ("pdf", "packet.pdf", "application/pdf", pdf_bytes),
            ],
        )

        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request(
            "POST",
            "/api/import",
            body=body,
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Content-Length": str(len(body)),
            },
        )
        resp = conn.getresponse()
        payload = json.loads(resp.read().decode("utf-8", errors="replace"))

        assert resp.status == 200
        assert payload["meeting_id"] == expected_meeting_id

        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/api/meetings")
        resp = conn.getresponse()
        data = json.loads(resp.read().decode("utf-8", errors="replace"))
        assert resp.status == 200
        matches = [m for m in data.get("meetings", []) if m.get("meeting_id") == expected_meeting_id]
        assert matches
        assert matches[0].get("meeting_date") == "2026-01-23"
        assert "City Hall" in str(matches[0].get("meeting_location") or "")

        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", f"/api/meetings/{expected_meeting_id}")
        resp = conn.getresponse()
        detail = json.loads(resp.read().decode("utf-8", errors="replace"))
        assert resp.status == 200
        assert detail["meeting"]["meeting_id"] == expected_meeting_id
        assert detail["meeting"].get("meeting_date") == "2026-01-23"
        assert "City Hall" in str(detail["meeting"].get("meeting_location") or "")
        # Import should have created and/or mirrored agenda items.
        assert "agenda_items" in detail.get("artifacts", {})
        assert isinstance(detail["artifacts"]["agenda_items"], list)

    finally:
        httpd.shutdown()
        httpd.server_close()
        t.join(timeout=2)


def test_k2_api_rerun_endpoint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Deterministic extraction including a keyword that will hit the profile rule.
    monkeypatch.setattr(
        "minutes_spike.store.extract_pdf_text_canonical",
        lambda _path: (
            "pymupdf",
            "1. CALL TO ORDER\nHello\n\n2.A. ORDINANCE / PUBLIC HEARING - CODE UPDATE\nAn Ordinance to amend the City Code.\n",
        ),
    )

    profile_path = tmp_path / "profile.yaml"
    profile_path.write_text(
        "rules:\n"
        "  - id: code\n"
        "    description: Code changes\n"
        "    type: keyword_any\n"
        "    enabled: true\n"
        "    keywords: [\"ordinance\"]\n"
        "    min_hits: 1\n"
        "output: {evidence: {snippet_chars: 120, max_snippets_per_rule: 3}}\n",
        encoding="utf-8",
    )

    store_dir = tmp_path / "store"
    store_dir.mkdir(parents=True, exist_ok=True)

    # Import via API.
    httpd, port, t = _start_server(store_dir=store_dir)
    try:
        boundary = "----councilsense-test-boundary"
        pdf_bytes = b"%PDF-1.4\n%fake\n"
        meeting_id = f"pdf_{hashlib.sha256(pdf_bytes).hexdigest()[:12]}"

        body = _multipart_body(
            boundary=boundary,
            parts=[("pdf", "packet.pdf", "application/pdf", pdf_bytes)],
        )
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request(
            "POST",
            "/api/import",
            body=body,
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Content-Length": str(len(body)),
            },
        )
        resp = conn.getresponse()
        resp.read()
        assert resp.status == 200

        # Now rerun Pass B/C via JSON endpoint.
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        rerun_body = json.dumps(
            {
                "profile": str(profile_path),
                "summarize_all_items": False,
                "classify_relevance": True,
                "summarize_meeting": True,
            }
        ).encode("utf-8")
        conn.request(
            "POST",
            f"/api/meetings/{meeting_id}/rerun",
            body=rerun_body,
            headers={
                "Content-Type": "application/json",
                "Content-Length": str(len(rerun_body)),
            },
        )
        resp = conn.getresponse()
        rerun_payload = json.loads(resp.read().decode("utf-8", errors="replace"))
        assert resp.status == 200
        assert rerun_payload["meeting_id"] == meeting_id
        assert rerun_payload["ran_pass_b"] is True
        assert rerun_payload["ran_pass_c"] is True

        # Detail should now include Pass B/C artifacts (via DB mirror or disk fallback).
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", f"/api/meetings/{meeting_id}")
        resp = conn.getresponse()
        detail = json.loads(resp.read().decode("utf-8", errors="replace"))
        assert resp.status == 200
        assert "things_you_care_about" in detail.get("artifacts", {})

    finally:
        httpd.shutdown()
        httpd.server_close()
        t.join(timeout=2)


def test_k2_api_rerun_regenerates_missing_agenda_items(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "minutes_spike.store.extract_pdf_text_canonical",
        lambda _path: (
            "pymupdf",
            "1. CALL TO ORDER\nHello\n\n2.A. ORDINANCE / PUBLIC HEARING - CODE UPDATE\nAn Ordinance to amend the City Code.\n",
        ),
    )

    profile_path = tmp_path / "profile.yaml"
    profile_path.write_text(
        "rules:\n"
        "  - id: code\n"
        "    description: Code changes\n"
        "    type: keyword_any\n"
        "    enabled: true\n"
        "    keywords: [\"ordinance\"]\n"
        "    min_hits: 1\n"
        "output: {evidence: {snippet_chars: 120, max_snippets_per_rule: 3}}\n",
        encoding="utf-8",
    )

    store_dir = tmp_path / "store"
    store_dir.mkdir(parents=True, exist_ok=True)

    httpd, port, t = _start_server(store_dir=store_dir)
    try:
        boundary = "----councilsense-test-boundary"
        pdf_bytes = b"%PDF-1.4\n%fake\n"
        meeting_id = f"pdf_{hashlib.sha256(pdf_bytes).hexdigest()[:12]}"

        body = _multipart_body(
            boundary=boundary,
            parts=[("pdf", "packet.pdf", "application/pdf", pdf_bytes)],
        )
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request(
            "POST",
            "/api/import",
            body=body,
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Content-Length": str(len(body)),
            },
        )
        resp = conn.getresponse()
        resp.read()
        assert resp.status == 200

        # Simulate a legacy/partial folder by deleting the import-time artifact.
        agenda_items_path = store_dir / meeting_id / "agenda_items.json"
        assert agenda_items_path.exists()
        agenda_items_path.unlink()

        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        rerun_body = json.dumps(
            {
                "profile": str(profile_path),
                "summarize_all_items": False,
                "classify_relevance": True,
                "summarize_meeting": True,
            }
        ).encode("utf-8")
        conn.request(
            "POST",
            f"/api/meetings/{meeting_id}/rerun",
            body=rerun_body,
            headers={
                "Content-Type": "application/json",
                "Content-Length": str(len(rerun_body)),
            },
        )
        resp = conn.getresponse()
        rerun_payload = json.loads(resp.read().decode("utf-8", errors="replace"))
        assert resp.status == 200
        assert rerun_payload["meeting_id"] == meeting_id

        # It should have been regenerated.
        assert agenda_items_path.exists()

    finally:
        httpd.shutdown()
        httpd.server_close()
        t.join(timeout=2)


def test_k2_api_chat_is_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "minutes_spike.store.extract_pdf_text_canonical",
        lambda _path: ("pymupdf", "1. CALL TO ORDER\nHello\n"),
    )

    # Stub answer_question to avoid depending on the chat pipeline details.
    monkeypatch.setattr(
        "minutes_spike.web.answer_question",
        lambda **_kwargs: {"answer": "ok", "citations": []},
    )

    store_dir = tmp_path / "store"
    store_dir.mkdir(parents=True, exist_ok=True)

    httpd, port, t = _start_server(store_dir=store_dir)
    try:
        # Import via API.
        boundary = "----councilsense-test-boundary"
        pdf_bytes = b"%PDF-1.4\n%fake\n"
        meeting_id = f"pdf_{hashlib.sha256(pdf_bytes).hexdigest()[:12]}"

        body = _multipart_body(
            boundary=boundary,
            parts=[("pdf", "packet.pdf", "application/pdf", pdf_bytes)],
        )
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request(
            "POST",
            "/api/import",
            body=body,
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Content-Length": str(len(body)),
            },
        )
        resp = conn.getresponse()
        resp.read()
        assert resp.status == 200

        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        chat_body = json.dumps({"question": "hi"}).encode("utf-8")
        conn.request(
            "POST",
            f"/api/meetings/{meeting_id}/chat",
            body=chat_body,
            headers={
                "Content-Type": "application/json",
                "Content-Length": str(len(chat_body)),
            },
        )
        resp = conn.getresponse()
        data = json.loads(resp.read().decode("utf-8", errors="replace"))
        assert resp.status == 200
        assert data["answer"] == "ok"

    finally:
        httpd.shutdown()
        httpd.server_close()
        t.join(timeout=2)


def test_k2_api_meeting_detail_falls_back_to_disk_without_ingestion(tmp_path: Path) -> None:
    store_dir = tmp_path / "store"
    meeting_id = "pdf_deadbeefcaf0"
    meeting_dir = store_dir / meeting_id
    meeting_dir.mkdir(parents=True, exist_ok=True)

    # Create a minimal meeting.json but no ingestion.json.
    (meeting_dir / "meeting.json").write_text(
        json.dumps({"meeting_id": meeting_id, "source_files": [], "ingestion_metadata": {}}, indent=2) + "\n",
        encoding="utf-8",
    )

    httpd, port, t = _start_server(store_dir=store_dir)
    try:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", f"/api/meetings/{meeting_id}")
        resp = conn.getresponse()
        detail = json.loads(resp.read().decode("utf-8", errors="replace"))
        assert resp.status == 200
        assert detail["meeting"]["meeting_id"] == meeting_id
        assert "artifacts" in detail
    finally:
        httpd.shutdown()
        httpd.server_close()
        t.join(timeout=2)
