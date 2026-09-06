from fastapi import Header, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import SystemSetting


from app.config import settings


async def verify_admin(x_admin_key: str = Header(None), db: AsyncSession = Depends(get_db)):
    """Validates the admin passcode against database or environment variable (X_ADMIN_KEY / ADMIN_PASSCODE)."""
    stmt = select(SystemSetting.value).where(SystemSetting.key == "admin_passcode")
    res = await db.execute(stmt)
    expected = res.scalar_one_or_none()
    if not expected:
        expected = settings.admin_key

    if not expected or not x_admin_key or x_admin_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing admin passcode header (x-admin-key)"
        )
    return True
