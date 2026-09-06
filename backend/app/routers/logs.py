from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import PostLog, AgentStepLog
from app.schemas import PostLogRead, PostLogDetailRead
from app.routers.dependencies import verify_admin
from app.config import settings

router = APIRouter(prefix="/api/logs", tags=["Logs"])


@router.get("", response_model=List[PostLogRead])
async def list_public_logs(
    limit: int = 50,
    offset: int = 0,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Public Endpoint: No login required.
    Returns list of posted threads history with timestamp, product, affiliate link, and status.
    """
    stmt = select(PostLog).order_by(PostLog.created_at.desc()).offset(offset).limit(limit)
    if search:
        search_pattern = f"%{search}%"
        stmt = stmt.where(
            (PostLog.product_name.ilike(search_pattern)) |
            (PostLog.post_text.ilike(search_pattern))
        )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{log_id}", response_model=PostLogDetailRead, dependencies=[Depends(verify_admin)])
async def get_log_detail(log_id: int, db: AsyncSession = Depends(get_db)):
    """
    Admin Endpoint: Returns full execution details, step-by-step tool traces, LLM thoughts, and screenshots.
    """
    stmt = (
        select(PostLog)
        .options(selectinload(PostLog.steps))
        .where(PostLog.id == log_id)
    )
    result = await db.execute(stmt)
    log = result.scalar_one_or_none()
    if not log:
        raise HTTPException(status_code=404, detail="Log not found")
    return log


@router.delete("/{log_id}", dependencies=[Depends(verify_admin)])
async def delete_single_log(log_id: int, db: AsyncSession = Depends(get_db)):
    """Admin Endpoint: Delete a single post log and its execution steps."""
    stmt = select(PostLog).where(PostLog.id == log_id)
    result = await db.execute(stmt)
    log = result.scalar_one_or_none()
    if not log:
        raise HTTPException(status_code=404, detail="Log not found")

    from sqlalchemy import delete as sql_delete
    await db.execute(sql_delete(AgentStepLog).where(AgentStepLog.post_log_id == log_id))
    await db.delete(log)
    await db.commit()
    return {"success": True, "message": f"Log {log_id} deleted"}


@router.delete("", dependencies=[Depends(verify_admin)])
async def delete_all_logs(db: AsyncSession = Depends(get_db)):
    """Admin Endpoint: Delete all logs and step traces."""
    from sqlalchemy import delete as sql_delete
    await db.execute(sql_delete(AgentStepLog))
    await db.execute(sql_delete(PostLog))
    await db.commit()
    return {"success": True, "message": "All execution logs deleted"}


@router.get("/screenshots/{filename}")
async def get_screenshot(filename: str):
    """Serve screenshot images"""
    # Prevent path traversal
    safe_filename = Path(filename).name
    file_path = Path(settings.SCREENSHOTS_PATH) / safe_filename
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Screenshot not found")
    return FileResponse(str(file_path), media_type="image/png")

