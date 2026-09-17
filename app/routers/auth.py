from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.errors import DuplicateKeyError

from ..db import get_db
from ..deps import current_user
from ..models import Token, UserCreate, UserLogin, UserPublic
from ..security import create_access_token, hash_password, verify_password
from ..serializers import user_public

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=Token, status_code=status.HTTP_201_CREATED)
async def signup(body: UserCreate):
    doc = {
        "email": body.email.lower(),
        "password_hash": hash_password(body.password),
        "plan": "free",
        "credits": 0,
        "profile": {},                                   # filled by onboarding
        "onboarding": {"completed": False},
        "github": {"linked": False},
        "meta": {},
        "created_at": datetime.now(timezone.utc),
    }
    try:
        res = await get_db().users.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "An account with this email already exists.")
    doc["_id"] = res.inserted_id
    return Token(access_token=create_access_token(str(res.inserted_id)),
                 user=user_public(doc))


@router.post("/login", response_model=Token)
async def login(body: UserLogin):
    user = await get_db().users.find_one({"email": body.email.lower()})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password.")
    return Token(access_token=create_access_token(str(user["_id"])),
                 user=user_public(user))


@router.get("/me", response_model=UserPublic)
async def me(user: dict = Depends(current_user)):
    return user_public(user)
