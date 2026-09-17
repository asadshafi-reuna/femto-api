from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status

from ..db import get_db
from ..deps import current_user
from ..entitlements import is_unlocked
from ..models import ConversionCreate, ConversionPublic
from ..serializers import conversion_public

router = APIRouter(prefix="/conversions", tags=["conversions"])


@router.post("", response_model=ConversionPublic, status_code=status.HTTP_201_CREATED)
async def create_conversion(body: ConversionCreate, user: dict = Depends(current_user)):
    """Record a conversion as queued. The compiler worker picks it up, writes the
    generated C to blob storage, and flips status to done/failed."""
    doc = {
        "user_id": user["_id"],
        "name": body.name,
        "target": body.target,
        "quant": body.quant,
        "goal": body.goal,
        "source": body.source.model_dump(),
        "status": "queued",
        "artifact": {"ready": False, "files": []},
        "unlocked": False,
        "created_at": datetime.now(timezone.utc),
    }
    res = await get_db().conversions.insert_one(doc)
    doc["_id"] = res.inserted_id
    return conversion_public(doc, is_unlocked(user, doc))


@router.get("", response_model=list[ConversionPublic])
async def list_conversions(user: dict = Depends(current_user)):
    cur = get_db().conversions.find({"user_id": user["_id"]}).sort("created_at", -1)
    return [conversion_public(d, is_unlocked(user, d)) async for d in cur]


@router.get("/{conversion_id}", response_model=ConversionPublic)
async def get_conversion(conversion_id: str, user: dict = Depends(current_user)):
    try:
        oid = ObjectId(conversion_id)
    except Exception:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversion not found")
    doc = await get_db().conversions.find_one({"_id": oid, "user_id": user["_id"]})
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversion not found")
    return conversion_public(doc, is_unlocked(user, doc))
