import asyncio
import logging
import sqlite3
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from councilsense.api.auth import AuthMiddleware, UNAUTHORIZED_BODY, UnauthorizedError
from councilsense.api.profile import (
    InMemoryUserProfileRepository,
    UnsupportedCityError,
    UserBootstrapService,
    UserProfileService,
)
from councilsense.api.routes.governance_deletions import router as governance_deletions_router
from councilsense.api.routes.governance_exports import router as governance_exports_router
from councilsense.api.routes.meetings import router as meetings_router
from councilsense.api.routes.me import router as me_router
from councilsense.api.routes.notification_replay import router as notification_replay_router
from councilsense.app.discovery_sync import run_startup_discovery_sync
from councilsense.app.governance_deletions import GovernanceDeletionProcessor, GovernanceDeletionService
from councilsense.app.governance_exports import GovernanceExportProcessor, GovernanceExportService
from councilsense.app.meeting_processing_requests import MeetingProcessingRequestService
from councilsense.app.notification_dlq_replay import NotificationDlqReplayService
from councilsense.db import MeetingReadRepository, apply_migrations, seed_city_registry
from councilsense.app.settings import get_settings


LOCAL_CORS_ALLOW_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]
LOCAL_CORS_ALLOW_ORIGIN_REGEX = r"^https?://(?:localhost|127\.0\.0\.1|\[::1\]|\d{1,3}(?:\.\d{1,3}){3})(?::\d+)?$"
STARTUP_DISCOVERY_RETRY_DELAY_SECONDS = 1.0


logger = logging.getLogger(__name__)


async def _run_startup_discovery_sync_with_retry(*, connection: sqlite3.Connection, supported_city_ids: tuple[str, ...]):
    result = run_startup_discovery_sync(
        connection=connection,
        supported_city_ids=supported_city_ids,
    )
    if result.synced_count > 0 or not result.errors:
        logger.info(
            "Startup discovery sync finished: synced=%s reconciled=%s errors=%s",
            result.synced_count,
            result.reconciled_count,
            len(result.errors),
        )
        return result

    logger.warning(
        "Startup discovery sync failed on initial attempt; retrying once in %.1fs: %s",
        STARTUP_DISCOVERY_RETRY_DELAY_SECONDS,
        "; ".join(result.errors),
    )
    await asyncio.sleep(STARTUP_DISCOVERY_RETRY_DELAY_SECONDS)

    retry_result = run_startup_discovery_sync(
        connection=connection,
        supported_city_ids=supported_city_ids,
    )
    if retry_result.errors:
        logger.warning(
            "Startup discovery sync completed with errors after retry: synced=%s reconciled=%s errors=%s",
            retry_result.synced_count,
            retry_result.reconciled_count,
            "; ".join(retry_result.errors),
        )
    else:
        logger.info(
            "Startup discovery sync recovered on retry: synced=%s reconciled=%s",
            retry_result.synced_count,
            retry_result.reconciled_count,
        )
    return retry_result


def create_app() -> FastAPI:
    settings = get_settings()
    db_path = os.getenv("COUNCILSENSE_SQLITE_PATH", ":memory:")
    connection = sqlite3.connect(db_path, check_same_thread=False)
    connection.execute("PRAGMA foreign_keys = ON")
    apply_migrations(connection)
    seed_city_registry(connection)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if settings.runtime_env == "local" and db_path != ":memory:":
            app.state.discovery_startup_sync = await _run_startup_discovery_sync_with_retry(
                connection=connection,
                supported_city_ids=settings.supported_city_ids,
            )
        yield

    app = FastAPI(title="CouncilSense API", lifespan=lifespan)
    if settings.runtime_env == "local":
        app.add_middleware(
            CORSMiddleware,
            allow_origins=LOCAL_CORS_ALLOW_ORIGINS,
            allow_origin_regex=LOCAL_CORS_ALLOW_ORIGIN_REGEX,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    repository = InMemoryUserProfileRepository()
    app.state.bootstrap_service = UserBootstrapService(
        repository=repository,
        supported_city_ids=settings.supported_city_ids,
    )
    app.state.profile_service = UserProfileService(
        repository=repository,
        supported_city_ids=settings.supported_city_ids,
    )
    app.state.settings = settings
    app.state.db_connection = connection
    app.state.meeting_read_repository = MeetingReadRepository(connection)
    app.state.meeting_processing_request_service = MeetingProcessingRequestService(
        connection=connection,
        admission_control=settings.on_demand_processing_admission_control,
    )
    app.state.governance_export_service = GovernanceExportService(connection=connection)
    app.state.governance_deletion_service = GovernanceDeletionService(connection=connection)
    app.state.governance_export_processor = GovernanceExportProcessor(
        connection=connection,
        profile_service=app.state.profile_service,
    )
    app.state.governance_deletion_processor = GovernanceDeletionProcessor(
        connection=connection,
        profile_service=app.state.profile_service,
    )
    app.state.notification_dlq_replay_service = NotificationDlqReplayService(
        connection=connection,
        allow_permanent_invalid_override=settings.notification_replay_allow_permanent_invalid_override,
    )
    app.state.discovery_startup_sync = None

    @app.exception_handler(UnauthorizedError)
    async def _handle_unauthorized(_, __):
        return JSONResponse(status_code=401, content=UNAUTHORIZED_BODY)

    @app.exception_handler(UnsupportedCityError)
    async def _handle_unsupported_city(_, exc: UnsupportedCityError):
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "Unsupported home_city_id",
                    "details": {"home_city_id": exc.home_city_id},
                }
            },
        )

    app.add_middleware(AuthMiddleware, settings=settings)
    app.include_router(me_router)
    app.include_router(meetings_router)
    app.include_router(governance_exports_router)
    app.include_router(governance_deletions_router)
    app.include_router(notification_replay_router)
    return app


app = create_app()
