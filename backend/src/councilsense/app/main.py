from fastapi import FastAPI
from fastapi.responses import JSONResponse

from councilsense.api.auth import AuthMiddleware, UNAUTHORIZED_BODY, UnauthorizedError
from councilsense.api.routes.me import router as me_router
from councilsense.app.settings import get_settings


def create_app() -> FastAPI:
    app = FastAPI(title="CouncilSense API")

    @app.exception_handler(UnauthorizedError)
    async def _handle_unauthorized(_, __):
        return JSONResponse(status_code=401, content=UNAUTHORIZED_BODY)

    app.add_middleware(AuthMiddleware, settings=get_settings())
    app.include_router(me_router)
    return app


app = create_app()
