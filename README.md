# emitc API

The control-plane API for the ONNX→C compiler platform, written in **Python
(FastAPI)** and backed by **MongoDB**. It handles auth and conversion records.
It does **not** run the compiler — that's a separate worker (see "Architecture"
below).

## What it does

- `POST /auth/signup` — create account, returns a JWT
- `POST /auth/login` — verify credentials, returns a JWT
- `GET  /auth/me` — current user (requires `Authorization: Bearer <token>`)
- `POST /conversions` — record a conversion, mark it `queued`
- `GET  /conversions` — list the current user's conversions
- `GET  /conversions/{id}` — one conversion
- `GET  /health` — liveness check

Interactive API docs are auto-generated at `/docs` when the server is running.

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # then edit .env with your MongoDB URI + JWT secret
uvicorn app.main:app --reload
```

Open http://localhost:8000/docs to try the endpoints.

## MongoDB (Atlas free tier)

1. At cloud.mongodb.com create a **free M0 cluster** (choose an Azure region).
2. Add a database user, and allow-list your IP (or 0.0.0.0/0 while testing).
3. Copy the `mongodb+srv://...` connection string into `MONGODB_URI` in `.env`.

The DB only stores metadata (users, conversion records) — model files belong in
blob storage — so 512 MB is plenty to start.

## Deploy to Azure

Two good options. Both build from the included `Dockerfile`.

**A. Azure Container Apps** (recommended — scales to zero, cheap when idle)
```bash
az containerapp up \
  --resource-group emitc-rg \
  --name emitc-api \
  --ingress external --target-port 8000 \
  --source .
```
Then set env vars (MONGODB_URI, JWT_SECRET, CORS_ORIGINS, DB_NAME) in the
Container App's configuration.

**B. Azure App Service (Python)** — no Docker needed
Deploy the code, then set the startup command:
```
gunicorn -w 2 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000 app.main:app
```
(On Python 3.14+ App Service auto-detects FastAPI and this isn't required.)
Set the same env vars under Configuration → Application settings.

Whichever you pick, put your MongoDB URI and JWT secret in the platform's
environment settings — never commit `.env`.

## Wire the frontend to this API

In the frontend project (`emitc-web`), replace the mocked functions in
`src/lib/api.js` with `fetch()` calls to this API's base URL, sending the JWT
in an `Authorization: Bearer <token>` header. Set `CORS_ORIGINS` here to the
frontend's domain so the browser is allowed to call it.

## Architecture: where the compiler fits

This API records a conversion as `queued` and returns immediately. A separate
**Python compiler worker** (on a VPS or a container with more resources) is what
actually:

1. pulls the `.onnx` from blob storage,
2. runs your ONNX→C toolchain in a sandbox with a timeout,
3. writes `model.c`/`model.h` back to storage,
4. updates the conversion document to `building` → `done`/`failed`.

Keeping the compiler out of this API means a slow build never blocks a login,
and you can scale compiler workers independently. The queue + worker aren't in
this repo yet — the `POST /conversions` handler marks the seam with a comment.

## Structure

```
app/
  main.py          FastAPI app, CORS, router wiring, /health
  config.py        settings from environment
  db.py            lazy Motor (async MongoDB) client + indexes
  security.py      bcrypt password hashing + JWT
  models.py        Pydantic request/response schemas
  deps.py          current-user dependency (Bearer token)
  routers/
    auth.py        signup, login, me
    conversions.py create, list, get
Dockerfile         prod image (gunicorn + uvicorn workers)
requirements.txt
.env.example
```
