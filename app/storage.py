"""
Artifact storage.

Generated C never lives in MongoDB — Mongo holds only metadata. The bytes go to
Azure Blob Storage in a PRIVATE container. Browsers never get a blob URL
directly; they get a short-lived SAS (signed) URL minted by the API only after
an entitlement check. That way a download link can't be shared or guessed, and
it expires on its own.

Layout inside the container:
    models/{user_id}/{conversion_id}/model.onnx     <- the uploaded input
    artifacts/{user_id}/{conversion_id}/femto.zip   <- the generated C

If AZURE_STORAGE_CONNECTION_STRING isn't configured, this module runs in a
local no-op mode so the API still boots and tests pass.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from .config import settings

try:
    from azure.storage.blob import (
        BlobServiceClient, generate_blob_sas, BlobSasPermissions,
    )
    _SDK = True
except Exception:          # SDK not installed / not configured
    _SDK = False


def _client() -> Optional["BlobServiceClient"]:
    if not _SDK or not settings.azure_storage_connection_string:
        return None
    return BlobServiceClient.from_connection_string(
        settings.azure_storage_connection_string
    )


def model_key(user_id: str, conversion_id: str, filename: str = "model.onnx") -> str:
    return f"models/{user_id}/{conversion_id}/{filename}"


def artifact_key(user_id: str, conversion_id: str) -> str:
    return f"artifacts/{user_id}/{conversion_id}/femto.zip"


def upload_bytes(key: str, data: bytes, content_type: str = "application/octet-stream") -> bool:
    """Store bytes at key. Returns False when storage isn't configured."""
    svc = _client()
    if svc is None:
        return False
    blob = svc.get_blob_client(settings.blob_container, key)
    blob.upload_blob(data, overwrite=True, content_type=content_type)
    return True


def signed_url(key: str, minutes: int = 10, filename: str = "femto.zip") -> Optional[str]:
    """Mint a read-only URL that expires. None if storage isn't configured."""
    svc = _client()
    if svc is None:
        return None
    expiry = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    sas = generate_blob_sas(
        account_name=svc.account_name,
        container_name=settings.blob_container,
        blob_name=key,
        account_key=svc.credential.account_key,
        permission=BlobSasPermissions(read=True),
        expiry=expiry,
        content_disposition=f'attachment; filename="{filename}"',
    )
    return f"{svc.url}{settings.blob_container}/{key}?{sas}"


def storage_configured() -> bool:
    return _client() is not None
