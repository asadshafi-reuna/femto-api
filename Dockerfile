# syntax=docker/dockerfile:1
FROM python:3.11-slim

WORKDIR /code

# Install deps first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Azure sets $PORT; default to 8000 for local runs.
ENV PORT=8000
EXPOSE 8000

# Gunicorn with Uvicorn workers is the recommended way to run FastAPI in prod.
CMD ["sh", "-c", "gunicorn -w 2 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:${PORT} app.main:app"]
