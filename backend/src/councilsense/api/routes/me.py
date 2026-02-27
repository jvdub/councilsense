from typing import Annotated

from fastapi import APIRouter, Depends

from councilsense.api.auth import AuthenticatedUser, get_current_user

router = APIRouter(prefix="/v1", tags=["me"])


@router.get("/me")
def get_me(user: Annotated[AuthenticatedUser, Depends(get_current_user)]) -> dict:
    return {"user_id": user.user_id}


@router.get("/me/bootstrap")
def get_bootstrap(user: Annotated[AuthenticatedUser, Depends(get_current_user)]) -> dict:
    return {
        "user_id": user.user_id,
        "onboarding_required": True,
    }
