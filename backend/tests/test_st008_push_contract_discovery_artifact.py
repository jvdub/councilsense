from __future__ import annotations

from pathlib import Path


def test_st008_discovery_artifact_covers_capability_matrix_contract_and_recovery_states() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    discovery_path = repo_root / "docs" / "runbooks" / "st-008-push-capability-and-contract-discovery.md"

    assert discovery_path.exists()

    content = discovery_path.read_text(encoding="utf-8")

    assert "## Browser Capability Matrix" in content
    assert "## Push Subscription API Contract (MVP)" in content
    assert "GET /v1/me/push-subscriptions" in content
    assert "POST /v1/me/push-subscriptions" in content
    assert "DELETE /v1/me/push-subscriptions/{subscription_id}" in content
    assert "`invalid`" in content
    assert "`expired`" in content
    assert "`suppressed`" in content
    assert "## Recovery Mapping (State -> UX Action)" in content
