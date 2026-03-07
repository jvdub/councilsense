from __future__ import annotations

import json

import pytest

from councilsense.app.local_pipeline import (
    LocalPipelineOrchestrator,
    _ExtractedPayload,
    _MeetingMaterialContext,
    _evaluate_authority_policy,
)
from councilsense.app.quality_gate_rollout import resolve_rollout_config
from councilsense.app.summarization import ClaimEvidencePointer, SummarizationOutput, SummaryClaim
from councilsense.db import MeetingSummaryRepository, ProcessingRunRepository
from councilsense.testing.st025_fixtures import (
    ST025_FIXTURE_SCHEMA_VERSION,
    St025FixtureScenario,
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


@pytest.mark.parametrize(
    "fixture_id",
    [fixture.fixture_id for fixture in load_fixture_catalog()],
)
def test_st025_fixture_authority_policy_matches_catalog_and_is_deterministic(fixture_id: str) -> None:
    scenario = {fixture.fixture_id: fixture for fixture in load_fixture_catalog()}[fixture_id]
    connection = create_test_connection()
    seed_fixture_scenario(connection=connection, scenario=scenario)

    first_compose = assemble_fixture_compose(connection=connection, scenario=scenario)
    second_compose = assemble_fixture_compose(connection=connection, scenario=scenario)

    first_policy = _evaluate_authority_policy(compose_input=first_compose)
    second_policy = _evaluate_authority_policy(compose_input=second_compose)

    assert first_policy.authority_outcome == scenario.expected_policy.authority_outcome
    assert first_policy.publication_status == scenario.expected_policy.publication_status
    assert first_policy.reason_codes == scenario.expected_policy.confidence_reason_codes
    assert first_policy.to_metadata_payload() == second_policy.to_metadata_payload()


@pytest.mark.parametrize(
    "fixture_id",
    [fixture.fixture_id for fixture in load_fixture_catalog()],
)
def test_st025_summarize_and_publish_fixture_path_is_deterministic_and_persists_compose_authority_metadata(
    fixture_id: str,
) -> None:
    scenario = {fixture.fixture_id: fixture for fixture in load_fixture_catalog()}[fixture_id]
    connection = create_test_connection()
    seed_fixture_scenario(connection=connection, scenario=scenario)
    orchestrator = LocalPipelineOrchestrator(connection)
    rollout_config = resolve_rollout_config(environment="local", cohort="city-eagle-mountain-ut")

    observed_summarize_metadata: list[dict[str, object]] = []
    observed_publish_authority_metadata: list[dict[str, object]] = []
    observed_publish_reason_codes: list[list[str]] = []
    observed_publish_statuses: list[str] = []
    observed_confidence_labels: list[str] = []
    observed_summary_shapes: list[tuple[tuple[str, ...], tuple[str, ...]]] = []

    for run_id in (f"run-{fixture_id}-summarize-a", f"run-{fixture_id}-summarize-b"):
        ProcessingRunRepository(connection).create_pending_run(
            run_id=run_id,
            city_id="city-eagle-mountain-ut",
            cycle_id=f"cycle-{run_id}",
        )
        material_context = _fixture_material_context(scenario=scenario)
        extracted = _fixture_extract_payload(scenario=scenario)

        summarize_payload, summarize_status = orchestrator._summarize_stage(
            run_id=run_id,
            city_id="city-eagle-mountain-ut",
            meeting_id=scenario.meeting_id,
            source_id="source-st025-fixture",
            source_type=scenario.expected_compose.fallback_source_type,
            extracted=extracted,
            material_context=material_context,
            rollout_config=rollout_config,
            llm_provider="none",
            ollama_endpoint=None,
            ollama_model=None,
            ollama_timeout_seconds=30.0,
        )

        assert summarize_status == "processed"
        observed_summary_shapes.append(
            (
                tuple(summarize_payload.output.key_decisions),
                tuple(summarize_payload.output.key_actions),
            )
        )

        summarize_metadata = _load_stage_metadata(
            connection=connection,
            stage_name="summarize",
            run_id=run_id,
            meeting_id=scenario.meeting_id,
        )
        compose_metadata = summarize_metadata["compose"]
        assert compose_metadata["source_order"] == list(scenario.expected_compose.source_order)
        assert compose_metadata["source_coverage"]["statuses"] == scenario.expected_compose.source_statuses
        assert compose_metadata["source_coverage"]["missing_source_types"] == list(
            scenario.expected_compose.missing_source_types
        )
        assert compose_metadata["source_coverage"]["partial_source_types"] == list(
            scenario.expected_compose.partial_source_types
        )
        assert compose_metadata["source_coverage"]["available_source_types"] == list(
            scenario.expected_compose.available_source_types
        )
        assert summarize_metadata["authority_policy"]["authority_outcome"] == scenario.expected_policy.authority_outcome
        assert summarize_metadata["authority_policy"]["publication_status"] == scenario.expected_policy.publication_status
        assert summarize_metadata["authority_policy"]["reason_codes"] == list(
            scenario.expected_policy.confidence_reason_codes
        )
        observed_summarize_metadata.append(summarize_metadata)

        publish_stage = orchestrator._publish_stage(
            run_id=run_id,
            city_id="city-eagle-mountain-ut",
            source_id="source-st025-fixture",
            source_type=scenario.expected_compose.fallback_source_type,
            meeting_id=scenario.meeting_id,
            output=summarize_payload.output,
            source_text=extracted.text,
            material_context=material_context,
            authority_policy=summarize_payload.authority_policy,
            extract_status="processed",
            summarize_status=summarize_status,
            summarize_fallback_used=False,
            rollout_config=rollout_config,
        )

        observed_publish_statuses.append(str(publish_stage["status"]))
        observed_publish_reason_codes.append(list(publish_stage["metadata"]["quality_gate_reason_codes"]))
        observed_publish_authority_metadata.append(dict(publish_stage["metadata"]["authority_policy"]))

        publication = MeetingSummaryRepository(connection).connection.execute(
            """
            SELECT publication_status, confidence_label, version_no
            FROM summary_publications
            WHERE processing_run_id = ?
            """,
            (run_id,),
        ).fetchone()
        assert publication is not None
        assert str(publication[0]) == scenario.expected_policy.publication_status
        observed_confidence_labels.append(str(publication[1]))
        assert int(publication[2]) in {1, 2}

        publish_metadata = _load_stage_metadata(
            connection=connection,
            stage_name="publish",
            run_id=run_id,
            meeting_id=scenario.meeting_id,
        )
        assert publish_metadata["authority_policy"]["reason_codes"] == list(
            scenario.expected_policy.confidence_reason_codes
        )

    expected_quality_gate_codes = ["quality_gate_pass", *scenario.expected_policy.confidence_reason_codes]
    expected_confidence_label = (
        "high" if scenario.expected_policy.publication_status == "processed" else "limited_confidence"
    )

    assert observed_summarize_metadata[0]["compose"] == observed_summarize_metadata[1]["compose"]
    assert observed_summarize_metadata[0]["authority_policy"] == observed_summarize_metadata[1]["authority_policy"]
    assert observed_publish_authority_metadata == [
        observed_summarize_metadata[0]["authority_policy"],
        observed_summarize_metadata[1]["authority_policy"],
    ]
    assert observed_publish_statuses == [scenario.expected_policy.publication_status, scenario.expected_policy.publication_status]
    assert observed_publish_reason_codes == [expected_quality_gate_codes, expected_quality_gate_codes]
    assert observed_confidence_labels == [expected_confidence_label, expected_confidence_label]

    if fixture_id == "st025-conflict-minutes-authoritative":
        assert observed_summary_shapes == [
            (
                (
                    "Council adopted Ordinance 2026-12 on second reading after closing the public hearing.",
                    "Staff will publish the adopted ordinance and update the fee schedule before April 1.",
                ),
                (
                    "Council adopted Ordinance 2026-12 on second reading after closing the public hearing.",
                    "Staff will publish the adopted ordinance and update the fee schedule before April 1.",
                ),
            ),
            (
                (
                    "Council adopted Ordinance 2026-12 on second reading after closing the public hearing.",
                    "Staff will publish the adopted ordinance and update the fee schedule before April 1.",
                ),
                (
                    "Council adopted Ordinance 2026-12 on second reading after closing the public hearing.",
                    "Staff will publish the adopted ordinance and update the fee schedule before April 1.",
                ),
            ),
        ]
    elif fixture_id == "st025-conflict-unresolved-without-minutes":
        assert observed_summary_shapes == [((), ()), ((), ())]
    elif fixture_id == "st025-partial-agenda-preview-missing-minutes":
        assert observed_summary_shapes == [((), ()), ((), ())]
    else:
        assert all(summary_shape[0] for summary_shape in observed_summary_shapes)
        assert all(summary_shape[1] for summary_shape in observed_summary_shapes)


@pytest.mark.parametrize(
    "fixture_id",
    [
        "st025-conflict-unresolved-without-minutes",
        "st025-partial-agenda-preview-missing-minutes",
        "st025-partial-minutes-only-coverage",
        "st025-weak-precision-minutes-locators",
    ],
)
def test_st025_publish_stage_applies_authority_downgrade_and_preserves_reason_codes_across_reruns(
    fixture_id: str,
) -> None:
    scenario = {fixture.fixture_id: fixture for fixture in load_fixture_catalog()}[fixture_id]
    connection = create_test_connection()
    seed_fixture_scenario(connection=connection, scenario=scenario)
    orchestrator = LocalPipelineOrchestrator(connection)
    rollout_config = resolve_rollout_config(environment="local", cohort="city-eagle-mountain-ut")
    output = _sample_output()

    observed_reason_codes: list[list[str]] = []
    observed_statuses: list[str] = []

    for run_id in (f"run-{fixture_id}-a", f"run-{fixture_id}-b"):
        ProcessingRunRepository(connection).create_pending_run(
            run_id=run_id,
            city_id="city-eagle-mountain-ut",
            cycle_id=f"cycle-{run_id}",
        )
        compose_input = assemble_fixture_compose(connection=connection, scenario=scenario)
        authority_policy = _evaluate_authority_policy(compose_input=compose_input)

        stage = orchestrator._publish_stage(
            run_id=run_id,
            city_id="city-eagle-mountain-ut",
            source_id=None,
            source_type=None,
            meeting_id=scenario.meeting_id,
            output=output,
            source_text=compose_input.composed_text,
            material_context=_MeetingMaterialContext(
                document_kind=(scenario.expected_compose.fallback_source_type or "minutes"),
                meeting_date_iso=scenario.meeting_datetime_utc[:10],
                meeting_temporal_status="past",
            ),
            authority_policy=authority_policy,
            extract_status="processed",
            summarize_status="processed",
            summarize_fallback_used=False,
            rollout_config=rollout_config,
        )

        observed_statuses.append(str(stage["status"]))
        observed_reason_codes.append(list(stage["metadata"]["quality_gate_reason_codes"]))

        publication = MeetingSummaryRepository(connection).connection.execute(
            """
            SELECT publication_status, confidence_label
            FROM summary_publications
            WHERE processing_run_id = ?
            """,
            (run_id,),
        ).fetchone()
        assert publication is not None
        assert str(publication[0]) == scenario.expected_policy.publication_status
        assert str(publication[1]) == "limited_confidence"

        metadata_row = connection.execute(
            """
            SELECT metadata_json
            FROM processing_stage_outcomes
            WHERE id = ?
            """,
            (f"outcome-publish-{run_id}-{scenario.meeting_id}",),
        ).fetchone()
        assert metadata_row is not None
        metadata = json.loads(str(metadata_row[0]))
        assert metadata["authority_policy"]["reason_codes"] == list(scenario.expected_policy.confidence_reason_codes)

    expected_quality_gate_codes = ["quality_gate_pass", *scenario.expected_policy.confidence_reason_codes]
    assert observed_statuses == [scenario.expected_policy.publication_status, scenario.expected_policy.publication_status]
    assert observed_reason_codes == [expected_quality_gate_codes, expected_quality_gate_codes]


def _sample_output() -> SummarizationOutput:
    return SummarizationOutput.from_sections(
        summary="Council recorded a publishable meeting outcome.",
        key_decisions=["Recorded a meeting outcome."],
        key_actions=["Staff will publish a follow-up update."],
        notable_topics=["Transportation"],
        claims=(
            SummaryClaim(
                claim_text="Council recorded a meeting outcome.",
                evidence=(
                    ClaimEvidencePointer(
                        artifact_id="artifact://st025",
                        section_ref="minutes.section.1",
                        char_start=0,
                        char_end=34,
                        excerpt="Council recorded a meeting outcome.",
                    ),
                ),
                evidence_gap=False,
            ),
        ),
    )


def _fixture_material_context(*, scenario: St025FixtureScenario) -> _MeetingMaterialContext:
    return _MeetingMaterialContext(
        document_kind=(scenario.expected_compose.fallback_source_type or "minutes"),
        meeting_date_iso=scenario.meeting_datetime_utc[:10],
        meeting_temporal_status="past",
    )


def _fixture_extract_payload(*, scenario: St025FixtureScenario) -> _ExtractedPayload:
    return _ExtractedPayload(
        text=(scenario.expected_compose.fallback_text or "fixture extract placeholder"),
        artifact_id=f"artifact://{scenario.fixture_id}",
        section_ref="fixture.extract",
        metadata={"fixture_id": scenario.fixture_id},
    )


def _load_stage_metadata(
    *,
    connection,
    stage_name: str,
    run_id: str,
    meeting_id: str,
) -> dict[str, object]:
    row = connection.execute(
        """
        SELECT metadata_json
        FROM processing_stage_outcomes
        WHERE id = ?
        """,
        (f"outcome-{stage_name}-{run_id}-{meeting_id}",),
    ).fetchone()
    assert row is not None
    return json.loads(str(row[0]))