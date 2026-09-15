from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status

from ..db import get_db
from ..deps import current_user
from ..models import ConversionCreate, ConversionPublic

router = APIRouter(prefix="/conversions", tags=["conversions"])


def _public(doc: dict) -> ConversionPublic:
    return ConversionPublic(
        id=str(doc["_id"]),
        name=doc["name"],
        target=doc["target"],
        quant=doc["quant"],
        goal=doc.get("goal", "size"),
        status=doc["status"],
        flash=doc.get("flash"),
        ram=doc.get("ram"),
        error=doc.get("error"),
        created_at=doc["created_at"],
    )


@router.post("", response_model=ConversionPublic, status_code=status.HTTP_201_CREATED)
async def create_conversion(body: ConversionCreate, user: dict = Depends(current_user)):
    """Record a new conversion and mark it queued. In production this is where
    you'd upload the .onnx to blob storage and push a job onto the queue that
    the Python compiler worker (on the VPS/container) picks up. The worker then
    flips status to building -> done/failed and fills in flash/ram."""
    doc = {
        "user_id": user["_id"],
        "name": body.name,
        "target": body.target,
        "quant": body.quant,
        "goal": body.goal,
        "status": "queued",
        "created_at": datetime.now(timezone.utc),
    }
    res = await get_db().conversions.insert_one(doc)
    doc["_id"] = res.inserted_id
    return _public(doc)


@router.get("", response_model=list[ConversionPublic])
async def list_conversions(user: dict = Depends(current_user)):
    cur = get_db().conversions.find({"user_id": user["_id"]}).sort("created_at", -1)
    return [_public(d) async for d in cur]


@router.get("/{conversion_id}", response_model=ConversionPublic)
async def get_conversion(conversion_id: str, user: dict = Depends(current_user)):
    try:
        oid = ObjectId(conversion_id)
    except Exception:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversion not found")
    doc = await get_db().conversions.find_one({"_id": oid, "user_id": user["_id"]})
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversion not found")
    return _public(doc)
