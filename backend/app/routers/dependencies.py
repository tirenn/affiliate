from fastapi import Header, Query, HTTPException, status, Depends
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import SystemSetting


from app.config import settings


async def verify_admin(
    x_admin_key: Optional[str] = Header(None),
    admin_key: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """Validates the admin passcode against database or environment variable (X_ADMIN_KEY / ADMIN_PASSCODE)."""
    provided_key = x_admin_key or admin_key
    stmt = select(SystemSetting.value).where(SystemSetting.key == "admin_passcode")
    res = await db.execute(stmt)
    expected = res.scalar_one_or_none()
    if not expected:
        expected = settings.admin_key

    if not expected or not provided_key or provided_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing admin passcode (x-admin-key header or admin_key query parameter)"
        )
    return True
