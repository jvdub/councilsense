from __future__ import annotations

import sqlite3

import pytest

from councilsense.app.scheduler import (
    EnabledCityScheduler,
    InMemoryCityScanQueueProducer,
    NonOverlappingExecutionGuard,
    run_scheduler_cycle,
)
from councilsense.db import PILOT_CITY_ID, apply_migrations, seed_city_registry


@pytest.fixture
def connection() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()


def test_scheduler_enqueues_one_scan_per_enabled_city_each_cycle(connection: sqlite3.Connection) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)

    connection.execute(
        """
        INSERT INTO cities (id, slug, name, state_code, timezone, enabled, priority_tier)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "city-second",
            "second-city-ut",
            "Second City",
            "UT",
            "America/Denver",
            1,
            2,
        ),
    )
    connection.execute(
        """
        INSERT INTO cities (id, slug, name, state_code, timezone, enabled, priority_tier)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "city-disabled",
            "disabled-city-ut",
            "Disabled City",
            "UT",
            "America/Denver",
            0,
            3,
        ),
    )

    queue = InMemoryCityScanQueueProducer()

    enqueued_city_ids = run_scheduler_cycle(
        connection=connection,
        queue_producer=queue,
        cycle_id="2026-02-27T00:00:00Z",
    )

    assert enqueued_city_ids == (PILOT_CITY_ID, "city-second")
    assert queue.enqueued_actions == [
        type(queue.enqueued_actions[0])(city_id=PILOT_CITY_ID, cycle_id="2026-02-27T00:00:00Z"),
        type(queue.enqueued_actions[0])(city_id="city-second", cycle_id="2026-02-27T00:00:00Z"),
    ]


def test_scheduler_enqueue_is_independent_of_subscriber_rows(connection: sqlite3.Connection) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)

    queue = InMemoryCityScanQueueProducer()

    enqueued_city_ids = run_scheduler_cycle(
        connection=connection,
        queue_producer=queue,
        cycle_id="2026-02-27T01:00:00Z",
    )

    assert enqueued_city_ids == (PILOT_CITY_ID,)
    assert [action.city_id for action in queue.enqueued_actions] == [PILOT_CITY_ID]


def test_scheduler_noops_when_overlap_guard_cannot_acquire(connection: sqlite3.Connection) -> None:
    apply_migrations(connection)
    seed_city_registry(connection)

    queue = InMemoryCityScanQueueProducer()
    overlap_guard = NonOverlappingExecutionGuard()
    assert overlap_guard.try_acquire() is True

    scheduler = EnabledCityScheduler(
        city_reader=type(
            "_CityReader",
            (),
            {"list_enabled_city_ids": staticmethod(lambda: (PILOT_CITY_ID,))},
        )(),
        queue_producer=queue,
        overlap_guard=overlap_guard,
    )

    enqueued_city_ids = scheduler.enqueue_enabled_city_scans(cycle_id="2026-02-27T02:00:00Z")

    assert enqueued_city_ids == ()
    assert queue.enqueued_actions == []
    overlap_guard.release()
