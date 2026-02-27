from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from councilsense.api.auth import AuthenticatedUser, get_current_user
from councilsense.api.profile import UserBootstrapService

router = APIRouter(prefix="/v1", tags=["me"])


class OnboardingCitySelectionRequest(BaseModel):
    home_city_id: str


def get_bootstrap_service(request: Request) -> UserBootstrapService:
    return request.app.state.bootstrap_service


@router.get("/me")
def get_me(user: Annotated[AuthenticatedUser, Depends(get_current_user)]) -> dict:
    return {"user_id": user.user_id}


@router.get("/me/bootstrap")
def get_bootstrap(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    bootstrap_service: Annotated[UserBootstrapService, Depends(get_bootstrap_service)],
) -> dict:
    return bootstrap_service.get_bootstrap(user.user_id)


@router.patch("/me/bootstrap")
def set_bootstrap_home_city(
    payload: OnboardingCitySelectionRequest,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    bootstrap_service: Annotated[UserBootstrapService, Depends(get_bootstrap_service)],
) -> dict:
    return bootstrap_service.set_home_city(user.user_id, payload.home_city_id)
