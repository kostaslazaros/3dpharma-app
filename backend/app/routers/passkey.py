"""
Passkey authentication router
Handles passkey validation and storage
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/passkey", tags=["passkey"])

# Path to passkey store file (in backend root directory)
STORE_FILE = Path(__file__).parent.parent.parent / "passkey_store.json"

# Base62 alphabet
_B62 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"


def _b62_encode(data: bytes) -> str:
    """Encode bytes to base62 string"""
    n = int.from_bytes(data, "big")
    if n == 0:
        return _B62[0]
    result = []
    while n:
        result.append(_B62[n % 62])
        n //= 62
    return "".join(reversed(result))


def _b62_decode(s: str) -> Optional[bytes]:
    """Decode base62 string to bytes"""
    try:
        n = 0
        for ch in s:
            n = n * 62 + _B62.index(ch)
        length = (n.bit_length() + 7) // 8 or 1
        return n.to_bytes(length, "big")
    except (ValueError, OverflowError):
        return None


def _encode(raw: str) -> str:
    """Encode string to base62"""
    return _b62_encode(raw.encode())


def _decode(token: str) -> Optional[str]:
    """Decode base62 token to string"""
    try:
        decoded_bytes = _b62_decode(token)
        if decoded_bytes is None:
            return None
        return decoded_bytes.decode()
    except Exception:
        return None


def _load_store() -> Dict:
    """Load passkey store from file"""
    if STORE_FILE.exists():
        try:
            with open(STORE_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def _save_store(store: Dict):
    """Save passkey store to file"""
    try:
        # Ensure directory exists
        STORE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(STORE_FILE, "w") as f:
            json.dump(store, f, indent=2)
    except IOError as e:
        print(f"Warning: Could not save passkey store: {e}")


class PasskeyValidateRequest(BaseModel):
    passkey: str


class PasskeyValidateResponse(BaseModel):
    valid: bool
    message: str


@router.post("/validate", response_model=PasskeyValidateResponse)
async def validate_passkey(request: PasskeyValidateRequest):
    """
    Validate a passkey and track first use
    
    Passkey format (before encoding): <8-char-random-id>|<duration>
    - duration = "L" for lifetime, or number of hours (e.g., "2", "24")
    """
    token = request.passkey.strip()
    
    if not token:
        raise HTTPException(status_code=400, detail="Passkey is required")
    
    # Decode passkey
    raw = _decode(token)
    if not raw or "|" not in raw:
        return PasskeyValidateResponse(
            valid=False,
            message="Invalid passkey format."
        )
    
    rand_id, duration_tag = raw.split("|", 1)
    
    # Parse duration
    duration_hours: Optional[float]
    if duration_tag == "L":
        duration_hours = None  # Lifetime
    else:
        try:
            duration_hours = float(duration_tag)
        except ValueError:
            return PasskeyValidateResponse(
                valid=False,
                message="Invalid passkey format."
            )
    
    # Load store
    store = _load_store()
    
    # Check if passkey has been used before
    if rand_id not in store:
        # First use - record timestamp
        store[rand_id] = {"first_used": datetime.now(timezone.utc).isoformat()}
        _save_store(store)
        return PasskeyValidateResponse(
            valid=True,
            message="Access granted."
        )
    
    # Passkey has been used before
    if duration_hours is None:
        # Lifetime key
        return PasskeyValidateResponse(
            valid=True,
            message="Access granted (lifetime key)."
        )
    
    # Check if still valid
    first_used = datetime.fromisoformat(store[rand_id]["first_used"])
    elapsed_hours = (datetime.now(timezone.utc) - first_used).total_seconds() / 3600
    
    if elapsed_hours <= duration_hours:
        return PasskeyValidateResponse(
            valid=True,
            message="Access granted."
        )
    
    # Expired
    return PasskeyValidateResponse(
        valid=False,
        message=(
            f"Passkey expired. It was valid for {int(duration_hours)}h from first use "
            f"({first_used.strftime('%Y-%m-%d %H:%M UTC')})."
        )
    )
