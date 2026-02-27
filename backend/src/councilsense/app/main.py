from fastapi import FastAPI
from fastapi.responses import JSONResponse

from councilsense.api.auth import AuthMiddleware, UNAUTHORIZED_BODY, UnauthorizedError
from councilsense.api.profile import (
    InMemoryUserProfileRepository,
    UnsupportedCityError,
    UserBootstrapService,
    UserProfileService,
)
from councilsense.api.routes.me import router as me_router
from councilsense.app.settings import get_settings


def create_app() -> FastAPI:
    app = FastAPI(title="CouncilSense API")
    settings = get_settings()
    repository = InMemoryUserProfileRepository()
    app.state.bootstrap_service = UserBootstrapService(
        repository=repository,
        supported_city_ids=settings.supported_city_ids,
    )
    app.state.profile_service = UserProfileService(
        repository=repository,
        supported_city_ids=settings.supported_city_ids,
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
    return app


app = create_app()
