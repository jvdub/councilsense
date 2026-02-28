import sqlite3
import os

from fastapi import FastAPI
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
from councilsense.app.governance_deletions import GovernanceDeletionProcessor, GovernanceDeletionService
from councilsense.app.governance_exports import GovernanceExportProcessor, GovernanceExportService
from councilsense.app.notification_dlq_replay import NotificationDlqReplayService
from councilsense.db import MeetingReadRepository, apply_migrations, seed_city_registry
from councilsense.app.settings import get_settings


def create_app() -> FastAPI:
    app = FastAPI(title="CouncilSense API")
    settings = get_settings()
    db_path = os.getenv("COUNCILSENSE_SQLITE_PATH", ":memory:")
    connection = sqlite3.connect(db_path, check_same_thread=False)
    connection.execute("PRAGMA foreign_keys = ON")
    apply_migrations(connection)
    seed_city_registry(connection)

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
