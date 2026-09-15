from bson import ObjectId
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .db import get_db
from .security import decode_token

bearer = HTTPBearer(auto_error=True)


async def current_user(creds: HTTPAuthorizationCredentials = Depends(bearer)) -> dict:
    """Decode the Bearer token, load the user, and return the DB document.
    Raises 401 if the token is missing, invalid, or the user no longer exists."""
    try:
        payload = decode_token(creds.credentials)
        user_id = payload["sub"]
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")

    try:
        oid = ObjectId(user_id)
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token subject")

    user = await get_db().users.find_one({"_id": oid})
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    return user
