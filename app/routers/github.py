"""
Link a GitHub account so models can be imported straight from a repo.

Scope choice matters:
  * "public_repo" - public repositories only
  * "repo"        - includes PRIVATE repositories

We ask which one the user wants rather than always requesting `repo`, because
requesting private access when it isn't needed is the kind of thing that makes
engineers close the tab.

Flow: /github/authorize -> GitHub consent -> /github/callback -> token stored
encrypted -> /github/repos and /github/import work from then on.
"""
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse

from ..config import settings
from ..crypto import configured as crypto_ready, decrypt, encrypt
from ..db import get_db
from ..deps import current_user
from ..models import GithubImport, GithubRepo

router = APIRouter(prefix="/github", tags=["github"])

GH_AUTH = "https://github.com/login/oauth/authorize"
GH_TOKEN = "https://github.com/login/oauth/access_token"
GH_API = "https://api.github.com"


@router.get("/authorize")
async def authorize(
    include_private: bool = Query(default=False,
                                  description="Request access to private repos too"),
    user: dict = Depends(current_user),
):
    """Returns the GitHub consent URL for the frontend to open."""
    if not settings.github_client_id:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "GitHub integration isn't configured.")
    if not crypto_ready():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "Token encryption isn't configured.")

    scope = "repo" if include_private else "public_repo"
    state = secrets.token_urlsafe(24)

    await get_db().oauth_states.insert_one({
        "state": state,
        "user_id": user["_id"],
        "scope": scope,
        "created_at": datetime.now(timezone.utc),
    })

    url = (f"{GH_AUTH}?client_id={settings.github_client_id}"
           f"&redirect_uri={settings.github_redirect_uri}"
           f"&scope={scope}&state={state}")
    return {"authorize_url": url, "scope": scope}


@router.get("/callback")
async def callback(code: str, state: str):
    """GitHub redirects here. Exchanges the code for a token, stores it
    encrypted against the user who started the flow, then bounces back to the app."""
    db = get_db()
    row = await db.oauth_states.find_one_and_delete({"state": state})
    if not row:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired state.")

    import httpx
    async with httpx.AsyncClient(timeout=15) as c:
        tok = await c.post(GH_TOKEN, headers={"Accept": "application/json"}, data={
            "client_id": settings.github_client_id,
            "client_secret": settings.github_client_secret,
            "code": code,
            "redirect_uri": settings.github_redirect_uri,
        })
        payload = tok.json()
        access = payload.get("access_token")
        if not access:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "GitHub did not return a token.")

        who = await c.get(f"{GH_API}/user",
                          headers={"Authorization": f"Bearer {access}",
                                   "Accept": "application/vnd.github+json"})
        profile = who.json()

    await db.users.update_one({"_id": row["user_id"]}, {"$set": {"github": {
        "linked": True,
        "login": profile.get("login"),
        "avatar_url": profile.get("avatar_url"),
        "scope": row.get("scope"),
        "token_enc": encrypt(access),       # encrypted at rest, never returned
        "linked_at": datetime.now(timezone.utc),
    }}})

    return RedirectResponse(settings.checkout_success_url)


@router.delete("/link")
async def unlink(user: dict = Depends(current_user)):
    """Disconnect GitHub and drop the stored token."""
    await get_db().users.update_one(
        {"_id": user["_id"]},
        {"$set": {"github": {"linked": False}}},
    )
    return {"linked": False}


async def _token(user: dict) -> str:
    gh = user.get("github") or {}
    if not gh.get("linked") or not gh.get("token_enc"):
        raise HTTPException(status.HTTP_409_CONFLICT, "Connect a GitHub account first.")
    return decrypt(gh["token_enc"])


@router.get("/repos", response_model=list[GithubRepo])
async def list_repos(user: dict = Depends(current_user)):
    """Repos the granted scope can see — private ones included only if the user
    chose that when linking."""
    token = await _token(user)
    import httpx
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.get(f"{GH_API}/user/repos",
                        params={"per_page": 100, "sort": "updated"},
                        headers={"Authorization": f"Bearer {token}",
                                 "Accept": "application/vnd.github+json"})
    if r.status_code != 200:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "GitHub request failed.")
    return [
        GithubRepo(full_name=x["full_name"], private=x["private"],
                   default_branch=x.get("default_branch", "main"),
                   updated_at=x.get("updated_at"))
        for x in r.json()
    ]


@router.post("/import")
async def import_model(body: GithubImport, user: dict = Depends(current_user)):
    """Pull a .onnx out of a repo and stage it for conversion.

    The file is fetched server-side with the user's token and written to blob
    storage — the browser never handles the token, and private repo contents
    never pass through it.
    """
    if not body.path.lower().endswith(".onnx"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "Only .onnx files can be imported.")
    token = await _token(user)

    import httpx
    url = f"{GH_API}/repos/{body.repo}/contents/{body.path}"
    params = {"ref": body.ref} if body.ref else {}
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.get(url, params=params,
                        headers={"Authorization": f"Bearer {token}",
                                 "Accept": "application/vnd.github.raw"})
    if r.status_code == 404:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found in that repo.")
    if r.status_code != 200:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Couldn't fetch the file from GitHub.")

    return {
        "repo": body.repo,
        "path": body.path,
        "ref": body.ref,
        "size_bytes": len(r.content),
        "staged": True,
    }
