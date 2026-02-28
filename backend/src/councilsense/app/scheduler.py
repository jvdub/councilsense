from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from threading import Lock
from typing import Protocol
from uuid import uuid4

from councilsense.db import CityRegistryRepository, ConfiguredCitySelectionService, ProcessingRunRepository


class EnabledCityIdsReader(Protocol):
    def list_enabled_city_ids(self) -> tuple[str, ...]: ...


class CityScanQueueProducer(Protocol):
    def enqueue_city_scan(self, *, city_id: str, cycle_id: str, run_id: str) -> None: ...


class SchedulerOverlapGuard(Protocol):
    def try_acquire(self) -> bool: ...

    def release(self) -> None: ...


class NonOverlappingExecutionGuard:
    def __init__(self) -> None:
        self._lock = Lock()

    def try_acquire(self) -> bool:
        return self._lock.acquire(blocking=False)

    def release(self) -> None:
        if self._lock.locked():
            self._lock.release()


@dataclass(frozen=True)
class CityScanEnqueueAction:
    city_id: str
    cycle_id: str
    run_id: str


class InMemoryCityScanQueueProducer:
    def __init__(self) -> None:
        self.enqueued_actions: list[CityScanEnqueueAction] = []

    def enqueue_city_scan(self, *, city_id: str, cycle_id: str, run_id: str) -> None:
        self.enqueued_actions.append(CityScanEnqueueAction(city_id=city_id, cycle_id=cycle_id, run_id=run_id))


class EnabledCityScheduler:
    def __init__(
        self,
        city_reader: EnabledCityIdsReader,
        queue_producer: CityScanQueueProducer,
        *,
        run_repository: ProcessingRunRepository | None = None,
        overlap_guard: SchedulerOverlapGuard | None = None,
    ) -> None:
        self._city_reader = city_reader
        self._queue_producer = queue_producer
        self._run_repository = run_repository
        self._overlap_guard = overlap_guard

    def enqueue_enabled_city_scans(self, *, cycle_id: str) -> tuple[str, ...]:
        normalized_cycle_id = cycle_id.strip()
        if not normalized_cycle_id:
            raise ValueError("cycle_id must be non-empty")

        if self._overlap_guard is not None and not self._overlap_guard.try_acquire():
            return ()

        try:
            city_ids = self._city_reader.list_enabled_city_ids()
            for city_id in city_ids:
                run_id = f"run-{uuid4().hex}"
                if self._run_repository is not None:
                    self._run_repository.create_pending_run(
                        run_id=run_id,
                        city_id=city_id,
                        cycle_id=normalized_cycle_id,
                    )
                self._queue_producer.enqueue_city_scan(city_id=city_id, cycle_id=normalized_cycle_id, run_id=run_id)
            return city_ids
        finally:
            if self._overlap_guard is not None:
                self._overlap_guard.release()


def run_scheduler_cycle(
    *,
    connection: sqlite3.Connection,
    queue_producer: CityScanQueueProducer,
    cycle_id: str,
    overlap_guard: SchedulerOverlapGuard | None = None,
) -> tuple[str, ...]:
    city_reader = ConfiguredCitySelectionService(CityRegistryRepository(connection))
    scheduler = EnabledCityScheduler(
        city_reader=city_reader,
        queue_producer=queue_producer,
        run_repository=ProcessingRunRepository(connection),
        overlap_guard=overlap_guard,
    )
    return scheduler.enqueue_enabled_city_scans(cycle_id=cycle_id)
