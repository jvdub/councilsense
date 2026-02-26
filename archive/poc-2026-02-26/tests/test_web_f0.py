from __future__ import annotations

import hashlib
import http.client
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from minutes_spike.web import _Handler, render_meeting_list_html, sync_store_dir_to_db


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


def test_f0_meeting_list_has_upload_fields(tmp_path: Path) -> None:
    store_dir = tmp_path / "store"
    html = render_meeting_list_html(store_dir=store_dir)
    assert "action=\"/import\"" in html
    assert "name=\"pdf\"" in html
    assert "name=\"text\"" in html


def test_f0_import_endpoint_accepts_pdf_and_optional_text(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Avoid depending on real PDF parsing libs/content.
    monkeypatch.setattr(
        "minutes_spike.store.extract_pdf_text_canonical",
        lambda _path: ("pymupdf", "1. CALL TO ORDER\nHello\n"),
    )

    store_dir = tmp_path / "store"
    store_dir.mkdir(parents=True, exist_ok=True)

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    httpd.store_dir = store_dir  # type: ignore[attr-defined]

    sync_store_dir_to_db(store_dir=store_dir)

    t = threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    t.start()

    try:
        port = httpd.server_address[1]
        boundary = "----councilsense-test-boundary"

        pdf_bytes = b"%PDF-1.4\n%fake\n"
        expected_meeting_id = f"pdf_{hashlib.sha256(pdf_bytes).hexdigest()[:12]}"

        body = _multipart_body(
            boundary=boundary,
            parts=[
                ("pdf", "packet.pdf", "application/pdf", pdf_bytes),
                ("text", "minutes.txt", "text/plain", b"These are minutes.\n"),
            ],
        )

        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request(
            "POST",
            "/import",
            body=body,
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Content-Length": str(len(body)),
            },
        )
        resp = conn.getresponse()
        resp.read()  # drain

        assert resp.status == 303
        loc = resp.getheader("Location")
        assert loc == f"/meetings/{expected_meeting_id}"

        meeting_dir = store_dir / expected_meeting_id
        assert (meeting_dir / "meeting.json").exists()
        assert (meeting_dir / "ingestion.json").exists()
        assert (meeting_dir / "source.pdf").exists()
        # Optional text minutes should be stored when provided.
        assert (meeting_dir / "source.txt").exists()
        assert (meeting_dir / "extracted_text_from_txt.txt").exists()

    finally:
        httpd.shutdown()
        httpd.server_close()
        t.join(timeout=2)
