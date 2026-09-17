"""
Who is allowed to download a generated artifact.

The rule, in one place so it can't drift:

  * plan == "pro" or "enterprise"  -> every artifact unlocked
  * the conversion was explicitly unlocked (a paid single_unlock order)
  * the user has unspent credits   -> spending one unlocks that conversion
  * otherwise                      -> locked; the API returns a preview only

Free users still see the conversion, the footprint numbers, the warnings and a
truncated preview of the C. They just can't download the full source until they
unlock it. That keeps the product honest — you can evaluate before paying.
"""
from .db import get_db

PAID_PLANS = {"pro", "enterprise"}

PREVIEW_LINES = 40          # how much generated C a locked user can see


def plan_unlocks_everything(user: dict) -> bool:
    return user.get("plan", "free") in PAID_PLANS


def is_unlocked(user: dict, conversion: dict) -> bool:
    if plan_unlocks_everything(user):
        return True
    return bool(conversion.get("unlocked"))


async def spend_credit_to_unlock(user: dict, conversion_id) -> bool:
    """Atomically spend one credit and unlock the conversion.
    Returns False when the user has no credits."""
    db = get_db()
    res = await db.users.update_one(
        {"_id": user["_id"], "credits": {"$gte": 1}},
        {"$inc": {"credits": -1}},
    )
    if res.modified_count != 1:
        return False
    await db.conversions.update_one(
        {"_id": conversion_id, "user_id": user["_id"]},
        {"$set": {"unlocked": True, "unlock_source": "credit"}},
    )
    return True
