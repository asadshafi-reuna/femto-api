import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pymongo.errors import PyMongoError

from .config import settings
from .db import ensure_indexes
from .routers import artifacts, auth, billing, conversions, github, me

log = logging.getLogger("femto")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await ensure_indexes()
    except Exception as e:  # noqa: BLE001
        log.warning("Could not create indexes on startup: %s", e)
    yield


app = FastAPI(title="femto API", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(PyMongoError)
async def db_error_handler(request: Request, exc: PyMongoError):
    log.error("Database error on %s: %s", request.url.path, exc)
    return JSONResponse(status_code=503,
                        content={"detail": "Database unavailable. Please try again."})


app.include_router(auth.router)
app.include_router(me.router)
app.include_router(conversions.router)
app.include_router(artifacts.router)
app.include_router(billing.router)
app.include_router(github.router)


@app.get("/health", tags=["meta"])
async def health():
    return {"status": "ok"}
