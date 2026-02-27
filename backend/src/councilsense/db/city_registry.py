from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class CityConfig:
    id: str
    slug: str
    name: str
    state_code: str
    timezone: str
    priority_tier: int


@dataclass(frozen=True)
class CitySourceConfig:
    id: str
    city_id: str
    source_type: str
    source_url: str
    parser_name: str
    parser_version: str
    health_status: str
    last_success_at: str | None
    last_attempt_at: str | None
    failure_streak: int


@dataclass(frozen=True)
class EnabledCityConfig:
    city: CityConfig
    sources: tuple[CitySourceConfig, ...]


class CityRegistryRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def list_enabled_cities(self) -> tuple[CityConfig, ...]:
        rows = self._connection.execute(
            """
            SELECT id, slug, name, state_code, timezone, priority_tier
            FROM cities
            WHERE enabled = 1
            ORDER BY priority_tier ASC, id ASC
            """
        ).fetchall()
        return tuple(
            CityConfig(
                id=str(row[0]),
                slug=str(row[1]),
                name=str(row[2]),
                state_code=str(row[3]),
                timezone=str(row[4]),
                priority_tier=int(row[5]),
            )
            for row in rows
        )

    def list_enabled_sources_for_city(self, city_id: str) -> tuple[CitySourceConfig, ...]:
        rows = self._connection.execute(
            """
            SELECT
                cs.id,
                cs.city_id,
                cs.source_type,
                cs.source_url,
                cs.parser_name,
                cs.parser_version,
                cs.health_status,
                cs.last_success_at,
                cs.last_attempt_at,
                cs.failure_streak
            FROM city_sources cs
            JOIN cities c ON c.id = cs.city_id
            WHERE cs.city_id = ?
              AND c.enabled = 1
              AND cs.enabled = 1
            ORDER BY cs.source_type ASC, cs.id ASC
            """,
            (city_id,),
        ).fetchall()
        return tuple(
            CitySourceConfig(
                id=str(row[0]),
                city_id=str(row[1]),
                source_type=str(row[2]),
                source_url=str(row[3]),
                parser_name=str(row[4]),
                parser_version=str(row[5]),
                health_status=str(row[6]),
                last_success_at=str(row[7]) if row[7] is not None else None,
                last_attempt_at=str(row[8]) if row[8] is not None else None,
                failure_streak=int(row[9]),
            )
            for row in rows
        )


class ConfiguredCitySelectionService:
    def __init__(self, repository: CityRegistryRepository) -> None:
        self._repository = repository

    def list_enabled_cities(self) -> tuple[CityConfig, ...]:
        return self._repository.list_enabled_cities()

    def list_enabled_city_ids(self) -> tuple[str, ...]:
        cities = self.list_enabled_cities()
        return tuple(city.id for city in cities)

    def list_enabled_sources_for_city(self, city_id: str) -> tuple[CitySourceConfig, ...]:
        return self._repository.list_enabled_sources_for_city(city_id)

    def list_enabled_city_configs(self) -> tuple[EnabledCityConfig, ...]:
        cities = self.list_enabled_cities()
        return tuple(
            EnabledCityConfig(
                city=city,
                sources=self.list_enabled_sources_for_city(city.id),
            )
            for city in cities
        )