from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.errors import DuplicateKeyError

from ..db import get_db
from ..deps import current_user
from ..models import Token, UserCreate, UserLogin, UserPublic
from ..security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


def _public(user: dict) -> UserPublic:
    return UserPublic(
        id=str(user["_id"]),
        email=user["email"],
        company=user.get("company"),
        plan=user.get("plan", "free"),
    )


@router.post("/signup", response_model=Token, status_code=status.HTTP_201_CREATED)
async def signup(body: UserCreate):
    db = get_db()
    doc = {
        "email": body.email.lower(),
        "password_hash": hash_password(body.password),
        "company": body.company,
        "plan": "free",
    }
    try:
        res = await db.users.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists.")
    doc["_id"] = res.inserted_id
    return Token(access_token=create_access_token(str(res.inserted_id)), user=_public(doc))


@router.post("/login", response_model=Token)
async def login(body: UserLogin):
    user = await get_db().users.find_one({"email": body.email.lower()})
    if not user or not verify_password(body.password, user["password_hash"]):
        # Same message for both cases so we don't reveal which emails exist.
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password.")
    return Token(access_token=create_access_token(str(user["_id"])), user=_public(user))


@router.get("/me", response_model=UserPublic)
async def me(user: dict = Depends(current_user)):
    return _public(user)
