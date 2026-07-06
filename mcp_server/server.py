"""
AyuGuard MCP Server
====================
Exposes two tools via FastMCP over stdio transport:
  - get_patient_profile()      : Read the live health_profile.json
  - update_patient_profile()   : Deep-merge a patch dict into health_profile.json

The ADK agent spawns this file as a subprocess.
"""

import json
import copy
import sys
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

# ── Path resolution ──────────────────────────────────────────────────────────
# Always locate health_profile.json relative to THIS file,
# regardless of the caller's working directory.
HERE = Path(__file__).parent.resolve()
PROFILE_PATH = HERE / "health_profile.json"

# ── Logging (stderr only – stdout is reserved for MCP stdio transport) ───────
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s [MCP-Server] %(levelname)s: %(message)s",
)
log = logging.getLogger(__name__)

# ── FastMCP server instance ───────────────────────────────────────────────────
mcp = FastMCP(
    name="AyuGuard Patient Profile Server",
    instructions=(
        "Provides real-time access to the patient's dynamic health profile. "
        "Tools: get_patient_profile (read) and update_patient_profile (write). "
        "The profile drives all dietary, medication, and care decisions."
    ),
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_profile() -> dict:
    """Load and return the JSON profile from disk."""
    if not PROFILE_PATH.exists():
        log.error("health_profile.json not found at %s", PROFILE_PATH)
        raise FileNotFoundError(f"health_profile.json missing at {PROFILE_PATH}")
    with PROFILE_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def _save_profile(profile: dict) -> None:
    """Persist the profile dict to disk as formatted JSON."""
    with PROFILE_PATH.open("w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)
    log.info("Profile saved to %s", PROFILE_PATH)


def _deep_merge(base: dict, patch: dict) -> dict:
    """
    Deep-merge `patch` into `base`.
    - Dicts are merged recursively.
    - Lists REPLACE entirely (caller sends the full desired list).
    - Scalars are replaced.
    Returns a new merged dict (base is not mutated).
    """
    result = copy.deepcopy(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


# ── MCP Tools ─────────────────────────────────────────────────────────────────

@mcp.tool
def get_patient_profile() -> dict:
    """
    Retrieve the current patient health profile from the live JSON store.

    Returns the complete profile including:
    - patient demographics and language preference
    - chronic_conditions (e.g., Type 2 Diabetes, Hypertension)
    - medications with names, schedules, and reminder times
    - acute_events (active short-term conditions like diarrhea, fever)
    - dietary_restrictions and allergies
    - last_updated timestamp

    This is the SINGLE SOURCE OF TRUTH. Call this at the start of every
    patient interaction to get current, up-to-date health state.

    Returns:
        A dict containing the full patient profile and a 'status' key.
        On error, returns {'status': 'error', 'message': <reason>}.
    """
    try:
        profile = _load_profile()
        log.info("Profile read OK — patient: %s, acute_events: %s",
                 profile.get("patient", {}).get("name", "unknown"),
                 profile.get("acute_events", []))
        return {"status": "success", "profile": profile}
    except FileNotFoundError as e:
        return {"status": "error", "message": str(e)}
    except json.JSONDecodeError as e:
        return {"status": "error", "message": f"Malformed JSON: {e}"}
    except Exception as e:  # noqa: BLE001
        log.exception("Unexpected error reading profile")
        return {"status": "error", "message": str(e)}


@mcp.tool
def update_patient_profile(patch: dict) -> dict:
    """
    Update the patient health profile by merging a patch dictionary.

    Supports adding/removing any top-level or nested field.
    Lists are REPLACED entirely — to remove an item, send the list without it.
    Dicts are merged recursively — only provide the keys you want to change.

    COMMON USAGE PATTERNS:
    - Add an acute event:  patch = {"acute_events": ["diarrhea"]}
    - Clear acute events:  patch = {"acute_events": []}
    - Add a medication:    patch = {"medications": [...full updated list...]}
    - Add a condition:     patch = {"chronic_conditions": [...updated list...]}
    - Update language:     patch = {"patient": {"language": "English"}}

    Args:
        patch: A dict of keys/values to merge into the existing profile.
               This dict must follow the same schema as the full profile.
               All values are optional — only include what you want to change.

    Returns:
        A dict with 'status', 'updated_profile', and 'changes_applied'.
        On error, returns {'status': 'error', 'message': <reason>}.
    """
    try:
        current = _load_profile()
        updated = _deep_merge(current, patch)
        updated["last_updated"] = datetime.now().astimezone().isoformat()
        _save_profile(updated)

        log.info("Profile updated — patch keys: %s", list(patch.keys()))
        return {
            "status": "success",
            "updated_profile": updated,
            "changes_applied": list(patch.keys()),
            "last_updated": updated["last_updated"],
        }
    except FileNotFoundError as e:
        return {"status": "error", "message": str(e)}
    except TypeError as e:
        return {"status": "error", "message": f"Invalid patch format: {e}"}
    except Exception as e:  # noqa: BLE001
        log.exception("Unexpected error updating profile")
        return {"status": "error", "message": str(e)}


# ── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    log.info("AyuGuard MCP Server starting — profile at %s", PROFILE_PATH)
    mcp.run()  # stdio transport by default — ADK manages the subprocess lifecycle
