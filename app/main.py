import logging

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pymongo.errors import PyMongoError

from .config import settings
from .db import ensure_indexes
from .routers import auth, conversions

log = logging.getLogger("emitc")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create indexes on startup. Non-fatal: if the DB is briefly unreachable
    # the server still boots and will retry indexing on the next restart.
    try:
        await ensure_indexes()
    except Exception as e:  # noqa: BLE001
        log.warning("Could not create indexes on startup: %s", e)
    yield


app = FastAPI(title="emitc API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(PyMongoError)
async def db_error_handler(request: Request, exc: PyMongoError):
    # The database was unreachable or errored. Return a clean 503 instead of a
    # 500 stack trace so the frontend can show "service unavailable, retry".
    log.error("Database error on %s: %s", request.url.path, exc)
    return JSONResponse(status_code=503, content={"detail": "Database unavailable. Please try again."})


app.include_router(auth.router)
app.include_router(conversions.router)


@app.get("/health", tags=["meta"])
async def health():
    return {"status": "ok"}
