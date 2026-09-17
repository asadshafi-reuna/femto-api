"""Artifact access: preview for everyone, full download only when entitled."""
from datetime import datetime, timedelta, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status

from ..config import settings
from ..db import get_db
from ..deps import current_user
from ..entitlements import PREVIEW_LINES, is_unlocked, spend_credit_to_unlock
from ..models import DownloadGrant
from .. import storage

router = APIRouter(prefix="/artifacts", tags=["artifacts"])


async def _load(conversion_id: str, user: dict) -> dict:
    try:
        oid = ObjectId(conversion_id)
    except Exception:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversion not found")
    doc = await get_db().conversions.find_one({"_id": oid, "user_id": user["_id"]})
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversion not found")
    return doc


@router.get("/{conversion_id}/preview")
async def preview(conversion_id: str, user: dict = Depends(current_user)):
    """Always allowed. Locked users get the first N lines so they can judge the
    output quality before paying; unlocked users get the whole thing."""
    doc = await _load(conversion_id, user)
    if doc["status"] != "done":
        raise HTTPException(status.HTTP_409_CONFLICT, "This build hasn't finished yet.")

    unlocked = is_unlocked(user, doc)
    full = (doc.get("artifact") or {}).get("preview_text", "")
    lines = full.splitlines()

    if unlocked:
        return {"unlocked": True, "text": full, "truncated": False}
    return {
        "unlocked": False,
        "text": "\n".join(lines[:PREVIEW_LINES]),
        "truncated": len(lines) > PREVIEW_LINES,
        "total_lines": len(lines),
        "unlock_price_cents": settings.price_single_unlock_cents,
    }


@router.post("/{conversion_id}/unlock")
async def unlock_with_credit(conversion_id: str, user: dict = Depends(current_user)):
    """Spend one prepaid credit to unlock this artifact. 402 when out of credits,
    which is the frontend's cue to send the user to checkout."""
    doc = await _load(conversion_id, user)
    if is_unlocked(user, doc):
        return {"unlocked": True, "spent_credit": False}

    ok = await spend_credit_to_unlock(user, doc["_id"])
    if not ok:
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED,
            "No unlock credits left. Buy a pack or unlock this build.",
        )
    return {"unlocked": True, "spent_credit": True}


@router.get("/{conversion_id}/download", response_model=DownloadGrant)
async def download(conversion_id: str, user: dict = Depends(current_user)):
    """Mint a short-lived signed URL for the generated C.
    402 if the user hasn't unlocked it — this is the paywall."""
    doc = await _load(conversion_id, user)

    if doc["status"] != "done":
        raise HTTPException(status.HTTP_409_CONFLICT, "This build hasn't finished yet.")
    if not (doc.get("artifact") or {}).get("ready"):
        raise HTTPException(status.HTTP_409_CONFLICT, "No artifact was produced.")
    if not is_unlocked(user, doc):
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED,
            "This artifact is locked. Unlock it to download the full source.",
        )

    key = storage.artifact_key(str(user["_id"]), conversion_id)
    url = storage.signed_url(key, minutes=settings.download_url_minutes,
                             filename=f"{doc['name'].replace('.onnx', '')}-c.zip")
    if not url:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Artifact storage isn't configured yet.",
        )

    return DownloadGrant(
        url=url,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=settings.download_url_minutes),
        filename=f"{doc['name'].replace('.onnx', '')}-c.zip",
    )
