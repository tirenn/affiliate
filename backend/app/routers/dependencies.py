import time
import secrets
import logging
from typing import Optional, Dict, List
from fastapi import Header, Query, HTTPException, status, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import SystemSetting
from app.config import settings
from app.security import decrypt_value

logger = logging.getLogger("security.auth")

# Sliding-window rate limiter for failed admin authentication attempts:
# {client_ip: [timestamp1, timestamp2, ...]}
_failed_attempts: Dict[str, List[float]] = {}
RATE_LIMIT_WINDOW_SECONDS = 60
MAX_FAILED_ATTEMPTS = 5


def _clean_and_check_rate_limit(ip: str, now: float):
    """Checks if the client IP has exceeded failed login attempts in the rolling window."""
    if ip in _failed_attempts:
        # Keep only timestamps within the window
        valid_timestamps = [t for t in _failed_attempts[ip] if now - t < RATE_LIMIT_WINDOW_SECONDS]
        _failed_attempts[ip] = valid_timestamps

        if len(valid_timestamps) >= MAX_FAILED_ATTEMPTS:
            oldest = valid_timestamps[0]
            retry_after = max(int(RATE_LIMIT_WINDOW_SECONDS - (now - oldest)), 1)
            logger.warning(f"[AUTH BRUTE-FORCE DETECTED] IP {ip} locked out. {len(valid_timestamps)} failed attempts.")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many failed login attempts. Please wait {retry_after} seconds before retrying.",
                headers={"Retry-After": str(retry_after)}
            )


def _record_failure(ip: str, now: float):
    """Records a failed authentication attempt timestamp for the client IP."""
    if ip not in _failed_attempts:
        _failed_attempts[ip] = []
    _failed_attempts[ip].append(now)


def _record_success(ip: str):
    """Clears failed attempts on successful authentication."""
    _failed_attempts.pop(ip, None)


async def verify_admin(
    request: Request,
    x_admin_key: Optional[str] = Header(None),
    admin_key: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
) -> bool:
    """
    Validates admin passcode with:
    1. Sliding-window IP rate limiting (brute-force defense).
    2. Decryption of stored admin passcode in system_settings.
    3. Constant-time string comparison (timing-attack defense).
    """
    # Extract client IP (respecting proxy headers)
    client_ip = (
        request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        or (request.client.host if request.client else "unknown")
    )
    now = time.time()

    # 1. Check rate limit
    _clean_and_check_rate_limit(client_ip, now)

    # 2. Retrieve expected passcode
    stmt = select(SystemSetting.value).where(SystemSetting.key == "admin_passcode")
    res = await db.execute(stmt)
    expected = res.scalar_one_or_none()
    if expected:
        expected = decrypt_value(expected)
    if not expected:
        expected = settings.admin_key

    provided_key = x_admin_key or admin_key

    # 3. Constant-time verification
    is_valid = False
    if expected and provided_key:
        is_valid = secrets.compare_digest(provided_key.strip(), expected.strip())

    if not is_valid:
        _record_failure(client_ip, now)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing admin passcode"
        )

    # Success: clear failed counter
    _record_success(client_ip)
    return True
