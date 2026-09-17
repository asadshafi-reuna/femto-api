"""Profile, onboarding, and account endpoints. Everything here is the logged-in
user's own data — nothing is readable without a valid token."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from ..db import get_db
from ..deps import current_user
from ..models import OnboardingSubmit, Profile, UserPublic
from ..serializers import user_public

router = APIRouter(prefix="/me", tags=["profile"])


@router.get("", response_model=UserPublic)
async def get_me(user: dict = Depends(current_user)):
    """The whole profile for the account settings page. The Account screen
    should render from THIS, never from hardcoded values."""
    return user_public(user)


@router.post("/onboarding", response_model=UserPublic)
async def submit_onboarding(body: OnboardingSubmit, user: dict = Depends(current_user)):
    """Called once, on the final 'Finish' of the 7-question flow.
    Stores the answers plus the silently captured metadata."""
    profile = Profile(**body.model_dump(exclude={"locale", "referrer", "utm"}))
    now = datetime.now(timezone.utc)

    await get_db().users.update_one(
        {"_id": user["_id"]},
        {"$set": {
            "profile": profile.model_dump(),
            "onboarding": {
                "completed": True,
                "completed_at": now,
                "version": 1,
            },
            "meta.locale": body.locale,
            "meta.referrer": body.referrer,
            "meta.utm": body.utm,
        }},
    )
    fresh = await get_db().users.find_one({"_id": user["_id"]})
    return user_public(fresh)


@router.patch("", response_model=UserPublic)
async def update_profile(body: Profile, user: dict = Depends(current_user)):
    """Partial profile edit from the account settings page.
    Only fields actually sent are changed."""
    changes = {f"profile.{k}": v for k, v in body.model_dump(exclude_unset=True).items()}
    if changes:
        await get_db().users.update_one({"_id": user["_id"]}, {"$set": changes})
    fresh = await get_db().users.find_one({"_id": user["_id"]})
    return user_public(fresh)
