from __future__ import annotations

import http.client
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from minutes_spike.web import _Handler, render_meeting_list_html


def _multipart_body(*, boundary: str, field: str, filename: str, content_type: str, data: bytes) -> bytes:
    return (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'
        f"Content-Type: {content_type}\r\n\r\n"
    ).encode("utf-8") + data + f"\r\n--{boundary}--\r\n".encode("utf-8")


def test_f4_invalid_store_dir_renders_clear_error(tmp_path: Path) -> None:
    store_path = tmp_path / "store"
    store_path.write_text("not a dir", encoding="utf-8")

    html = render_meeting_list_html(store_dir=store_path)
    assert "Store directory error" in html
    assert str(store_path.resolve()) in html
    assert "not a directory" in html


def test_f4_import_blocked_when_store_dir_invalid(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Even if PDF extraction would succeed, invalid store_dir should block import.
    monkeypatch.setattr(
        "minutes_spike.store.extract_pdf_text_canonical",
        lambda _path: ("pymupdf", "1. CALL TO ORDER\nHello\n"),
    )

    store_path = tmp_path / "store"
    store_path.write_text("not a dir", encoding="utf-8")

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    httpd.store_dir = store_path  # type: ignore[attr-defined]

    t = threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    t.start()

    try:
        port = httpd.server_address[1]
        boundary = "----councilsense-test-boundary"
        body = _multipart_body(
            boundary=boundary,
            field="pdf",
            filename="packet.pdf",
            content_type="application/pdf",
            data=b"%PDF-1.4\n%fake\n",
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
        data = resp.read().decode("utf-8", errors="replace")

        assert resp.status == 500
        assert "Store directory error" in data

    finally:
        httpd.shutdown()
        httpd.server_close()
        t.join(timeout=2)
