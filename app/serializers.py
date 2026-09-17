"""Turn raw Mongo documents into the public shapes the API returns.
Kept in one place so a secret can't leak by accident — password_hash and the
GitHub access token are never included here."""
from .models import (
    ArtifactInfo, ConversionPublic, ConversionSource,
    GithubPublic, Profile, UserPublic,
)


def user_public(doc: dict) -> UserPublic:
    gh = doc.get("github") or {}
    return UserPublic(
        id=str(doc["_id"]),
        email=doc["email"],
        plan=doc.get("plan", "free"),
        profile=Profile(**(doc.get("profile") or {})),
        onboarding_completed=bool((doc.get("onboarding") or {}).get("completed")),
        github=GithubPublic(
            linked=bool(gh.get("linked")),
            login=gh.get("login"),
            avatar_url=gh.get("avatar_url"),
            scope=gh.get("scope"),
            linked_at=gh.get("linked_at"),
        ),
        credits=int(doc.get("credits", 0)),
        created_at=doc.get("created_at"),
    )


def conversion_public(doc: dict, unlocked: bool) -> ConversionPublic:
    art = doc.get("artifact") or {}
    return ConversionPublic(
        id=str(doc["_id"]),
        name=doc["name"],
        target=doc["target"],
        quant=doc.get("quant", "int8"),
        goal=doc.get("goal", "size"),
        status=doc["status"],
        flash=doc.get("flash"),
        ram=doc.get("ram"),
        error=doc.get("error"),
        source=ConversionSource(**(doc.get("source") or {})),
        artifact=ArtifactInfo(
            ready=bool(art.get("ready")),
            files=art.get("files", []),
            size_bytes=art.get("size_bytes"),
            sha256=art.get("sha256"),
            line_count=art.get("line_count"),
        ),
        unlocked=unlocked,
        created_at=doc["created_at"],
    )
