"""
AyuGuard GCS Client
====================
Uploads medical record files to Google Cloud Storage when the
GCS_BUCKET environment variable is set. Falls back to local disk
if GCS is unavailable or not configured.
"""
from __future__ import annotations
import os
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_GCS_BUCKET = os.environ.get("GCS_BUCKET", "")
_client = None
_init_attempted = False


def _get_client():
    global _client, _init_attempted
    if _init_attempted:
        return _client
    _init_attempted = True
    if not _GCS_BUCKET:
        logger.info("GCS_BUCKET not set — using local file storage.")
        return None
    try:
        from google.cloud import storage
        _client = storage.Client()
        logger.info(f"GCS client initialised — bucket: {_GCS_BUCKET}")
        return _client
    except Exception as e:
        logger.warning(f"GCS init failed ({e}) — falling back to local storage.")
        return None


def upload_file(local_path: Path, blob_name: str) -> Optional[str]:
    """
    Upload a local file to GCS. Returns the GCS URI (gs://...) or None on failure.
    Also keeps the local file as a fallback cache.
    """
    client = _get_client()
    if client is None:
        return None
    try:
        bucket = client.bucket(_GCS_BUCKET)
        blob = bucket.blob(blob_name)
        blob.upload_from_filename(str(local_path))
        uri = f"gs://{_GCS_BUCKET}/{blob_name}"
        logger.info(f"Uploaded to GCS: {uri}")
        return uri
    except Exception as e:
        logger.warning(f"GCS upload failed for {blob_name}: {e}")
        return None


def download_file(blob_name: str, dest_path: Path) -> bool:
    """
    Download a file from GCS to dest_path. Returns True on success.
    """
    client = _get_client()
    if client is None:
        return False
    try:
        bucket = client.bucket(_GCS_BUCKET)
        blob = bucket.blob(blob_name)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        blob.download_to_filename(str(dest_path))
        return True
    except Exception as e:
        logger.warning(f"GCS download failed for {blob_name}: {e}")
        return False


def gcs_available() -> bool:
    return _get_client() is not None


def bucket_name() -> str:
    return _GCS_BUCKET
