from __future__ import annotations

import json

from councilsense.app.local_pipeline import _extract_text_from_artifact_content


def test_extract_text_from_civicclerk_json_artifact() -> None:
    payload = {
        "source": "civicclerk_events",
        "selected_event_name": "City Council Meeting",
        "selected_event_date": "2026-02-17",
        "selected_file": {
            "type": "Agenda",
            "name": "Final Agenda",
            "publishOn": "2026-02-10T18:00:00Z",
        },
    }

    text, mode = _extract_text_from_artifact_content(json.dumps(payload))

    assert mode == "civicclerk_json_artifact"
    assert "City Council Meeting on 2026-02-17" in text
    assert "Agenda titled Final Agenda" in text
    assert "published on 2026-02-10T18:00:00Z" in text
