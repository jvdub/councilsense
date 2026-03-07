from __future__ import annotations

import pytest

from councilsense.testing.st025_fixtures import (
    ST025_FIXTURE_SCHEMA_VERSION,
    assemble_fixture_compose,
    collect_precision_signal_tags,
    create_test_connection,
    load_fixture_catalog,
    seed_fixture_scenario,
)


def test_st025_fixture_catalog_contains_required_scenarios_and_stable_order() -> None:
    first = load_fixture_catalog()
    second = load_fixture_catalog()

    assert len(first) == 5
    assert [fixture.fixture_id for fixture in first] == [
        "st025-conflict-minutes-authoritative",
        "st025-conflict-unresolved-without-minutes",
        "st025-partial-agenda-preview-missing-minutes",
        "st025-partial-minutes-only-coverage",
        "st025-weak-precision-minutes-locators",
    ]
    assert [fixture.stable_fixture_key for fixture in first] == [fixture.stable_fixture_key for fixture in second]
    assert {fixture.scenario_group for fixture in first} == {
        "source_conflict",
        "partial_coverage",
        "weak_precision",
    }


@pytest.mark.parametrize(
    ("fixture_id", "expected_source_origins"),
    [
        ("st025-conflict-minutes-authoritative", ("canonical", "canonical", "canonical")),
        ("st025-conflict-unresolved-without-minutes", ("missing", "canonical", "canonical")),
        ("st025-partial-agenda-preview-missing-minutes", ("missing", "fallback_extract", "missing")),
        ("st025-partial-minutes-only-coverage", ("canonical", "missing", "missing")),
        ("st025-weak-precision-minutes-locators", ("canonical", "canonical", "missing")),
    ],
)
def test_st025_fixture_scenarios_seed_and_compose_deterministically(
    fixture_id: str,
    expected_source_origins: tuple[str, str, str],
) -> None:
    scenario = {fixture.fixture_id: fixture for fixture in load_fixture_catalog()}[fixture_id]
    connection = create_test_connection()
    seed_fixture_scenario(connection=connection, scenario=scenario)

    first = assemble_fixture_compose(connection=connection, scenario=scenario)
    second = assemble_fixture_compose(connection=connection, scenario=scenario)

    assert first.source_order == scenario.expected_compose.source_order
    assert tuple(source.source_origin for source in first.sources) == expected_source_origins
    assert first.source_coverage.statuses == scenario.expected_compose.source_statuses
    assert first.source_coverage.missing_source_types == scenario.expected_compose.missing_source_types
    assert first.source_coverage.partial_source_types == scenario.expected_compose.partial_source_types
    assert first.source_coverage.available_source_types == scenario.expected_compose.available_source_types
    assert first.composed_text == second.composed_text
    assert first.source_coverage.coverage_checksum == second.source_coverage.coverage_checksum


def test_st025_fixture_catalog_encodes_expected_authority_and_confidence_outcomes() -> None:
    fixtures = {fixture.fixture_id: fixture for fixture in load_fixture_catalog()}

    assert fixtures["st025-conflict-minutes-authoritative"].expected_policy.authority_outcome == "minutes_authoritative"
    assert fixtures["st025-conflict-minutes-authoritative"].expected_policy.publication_status == "processed"
    assert fixtures["st025-conflict-minutes-authoritative"].expected_policy.confidence_reason_codes == ()

    assert fixtures["st025-conflict-unresolved-without-minutes"].expected_policy.confidence_reason_codes == (
        "missing_authoritative_minutes",
        "unresolved_source_conflict",
    )
    assert fixtures["st025-partial-agenda-preview-missing-minutes"].expected_policy.confidence_reason_codes == (
        "agenda_preview_only",
        "missing_authoritative_minutes",
    )
    assert fixtures["st025-partial-minutes-only-coverage"].expected_policy.confidence_reason_codes == (
        "supplemental_sources_missing",
    )
    assert fixtures["st025-weak-precision-minutes-locators"].expected_policy.confidence_reason_codes == (
        "weak_evidence_precision",
    )

    assert collect_precision_signal_tags(scenario=fixtures["st025-weak-precision-minutes-locators"]) == ("weak_precision",)


def test_st025_fixture_catalog_schema_constant_matches_manifest_contract() -> None:
    assert ST025_FIXTURE_SCHEMA_VERSION == "st025-source-conflict-partial-coverage-fixtures-v1"