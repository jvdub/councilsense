from typing import Annotated
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict

from councilsense.api.auth import AuthenticatedUser, get_current_user
from councilsense.api.profile import UNSET, UserBootstrapService, UserProfileService

router = APIRouter(prefix="/v1", tags=["me"])


class OnboardingCitySelectionRequest(BaseModel):
    home_city_id: str


class ProfileResponse(BaseModel):
    email: str | None
    home_city_id: str | None
    notifications_enabled: bool
    notifications_paused_until: datetime | None


class ProfilePatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    home_city_id: str | None = None
    notifications_enabled: bool | None = None
    notifications_paused_until: datetime | None = None


def get_bootstrap_service(request: Request) -> UserBootstrapService:
    return request.app.state.bootstrap_service


def get_profile_service(request: Request) -> UserProfileService:
    return request.app.state.profile_service


@router.get("/me")
def get_me(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    profile_service: Annotated[UserProfileService, Depends(get_profile_service)],
) -> ProfileResponse:
    profile = profile_service.get_profile(user.user_id)
    return ProfileResponse(
        email=user.email,
        home_city_id=profile.home_city_id,
        notifications_enabled=profile.notifications_enabled,
        notifications_paused_until=profile.notifications_paused_until,
    )


@router.patch("/me")
def patch_me(
    payload: ProfilePatchRequest,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    profile_service: Annotated[UserProfileService, Depends(get_profile_service)],
) -> ProfileResponse:
    home_city_id: str | object = UNSET
    notifications_enabled: bool | object = UNSET
    notifications_paused_until: datetime | None | object = UNSET

    if "home_city_id" in payload.model_fields_set:
        home_city_id = payload.home_city_id
    if "notifications_enabled" in payload.model_fields_set:
        notifications_enabled = payload.notifications_enabled
    if "notifications_paused_until" in payload.model_fields_set:
        notifications_paused_until = payload.notifications_paused_until

    profile = profile_service.patch_profile(
        user.user_id,
        home_city_id=home_city_id,
        notifications_enabled=notifications_enabled,
        notifications_paused_until=notifications_paused_until,
    )
    return ProfileResponse(
        email=user.email,
        home_city_id=profile.home_city_id,
        notifications_enabled=profile.notifications_enabled,
        notifications_paused_until=profile.notifications_paused_until,
    )


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
