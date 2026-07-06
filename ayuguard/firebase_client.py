"""
AyuGuard Firebase Client
=========================
Initialises the Firebase Admin SDK and returns a Firestore client.

Configuration (in ayuguard/.env):
  FIREBASE_SERVICE_ACCOUNT_PATH=firebase-service-account.json
  (relative to ayuguard/ directory, or absolute path)

If the service account is not configured or Firebase is unavailable,
get_firestore_client() returns None and all callers fall back to the
local JSON store automatically.
"""
from __future__ import annotations

import os
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_AGENT_DIR = Path(__file__).parent.resolve()
_db = None          # singleton Firestore client
_init_attempted = False


def get_firestore_client():
    """
    Return the Firestore client singleton, or None if Firebase is not configured.

    Priority:
      1. FIREBASE_SERVICE_ACCOUNT_JSON  — full JSON string (Cloud Run / Secret Manager)
      2. FIREBASE_SERVICE_ACCOUNT_PATH  — path to a JSON file (local dev)

    Always safe to call — will not raise on missing credentials.
    Callers should check `if db := get_firestore_client()` before using Firestore.
    """
    global _db, _init_attempted
    if _init_attempted:
        return _db
    _init_attempted = True

    try:
        import firebase_admin
        from firebase_admin import credentials, firestore

        cred = None

        # ── Option 1: Inline JSON via env var (Cloud Run / Secret Manager) ──
        sa_json_str = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()
        if sa_json_str:
            try:
                sa_dict = json.loads(sa_json_str)
                cred = credentials.Certificate(sa_dict)
                logger.info("AyuGuard Firebase: using FIREBASE_SERVICE_ACCOUNT_JSON env var.")
            except json.JSONDecodeError as e:
                logger.warning(f"AyuGuard Firebase: FIREBASE_SERVICE_ACCOUNT_JSON is not valid JSON ({e}).")

        # ── Option 2: File path (local dev) ──
        if cred is None:
            sa_path_env = os.environ.get("FIREBASE_SERVICE_ACCOUNT_PATH", "")
            if not sa_path_env:
                logger.info("AyuGuard Firebase: no credentials configured — using local JSON store.")
                return None
            sa_path = Path(sa_path_env)
            if not sa_path.is_absolute():
                sa_path = _AGENT_DIR / sa_path
            if not sa_path.exists():
                logger.warning(f"AyuGuard Firebase: service account not found at {sa_path} — using local JSON store.")
                return None
            cred = credentials.Certificate(str(sa_path))
            logger.info(f"AyuGuard Firebase: using file {sa_path}")

        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)

        _db = firestore.client()
        logger.info("AyuGuard Firebase: Firestore connected ✓")
        return _db

    except ImportError:
        logger.warning("firebase-admin not installed. Run: pip install firebase-admin")
        return None
    except Exception as exc:
        logger.warning(f"AyuGuard Firebase: init failed ({exc}) — using local JSON store.")
        return None


def is_firebase_available() -> bool:
    """Return True if Firestore is configured and reachable."""
    return get_firestore_client() is not None
