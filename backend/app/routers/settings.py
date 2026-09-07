import json
from pathlib import Path
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import SystemSetting
from app.schemas import SystemSettingsRead, SystemSettingsUpdate
from app.routers.dependencies import verify_admin
from app.config import settings
from app.scheduler.cron_runner import cron_scheduler

router = APIRouter(prefix="/api/settings", tags=["Settings"])


async def set_or_update(db: AsyncSession, key: str, value: str):
    result = await db.execute(select(SystemSetting).where(SystemSetting.key == key))
    setting = result.scalar_one_or_none()
    if setting:
        setting.value = value
    else:
        db.add(SystemSetting(key=key, value=value))


async def get_val(db: AsyncSession, key: str, fallback: str = "") -> str:
    result = await db.execute(select(SystemSetting).where(SystemSetting.key == key))
    setting = result.scalar_one_or_none()
    return setting.value if setting and setting.value is not None else fallback


@router.get("", response_model=SystemSettingsRead, dependencies=[Depends(verify_admin)])
async def get_settings(db: AsyncSession = Depends(get_db)):
    openrouter_key = await get_val(db, "openrouter_api_key", "")
    openrouter_model = await get_val(db, "openrouter_model", "openrouter/free")
    
    threads_user = await get_val(db, "threads_username", "")
    threads_pass = await get_val(db, "threads_password", "")
    proxy_url = await get_val(db, "proxy_url", "")
    threads_session_id = await get_val(db, "threads_session_id", "")
    
    sched_enabled = (await get_val(db, "scheduler_enabled", "false")).lower() == "true"
    
    window_str = await get_val(db, "scheduler_window_minutes", "60")
    posts_str = await get_val(db, "scheduler_posts_per_window", "10")
    min_comments_str = await get_val(db, "min_thread_comments", "50")
    min_likes_str = await get_val(db, "min_thread_likes", "100")
    
    window_min = int(window_str) if window_str.isdigit() else 60
    posts_count = max(int(posts_str) if posts_str.isdigit() else 10, 1)
    min_comments = int(min_comments_str) if min_comments_str.isdigit() else 50
    min_likes = int(min_likes_str) if min_likes_str.isdigit() else 100
    
    calc_interval = round(window_min / posts_count, 2)
    headless = (await get_val(db, "headless_browser", "true")).lower() == "true"

    session_file = Path(settings.SESSIONS_PATH) / "threads_session.json"
    session_file_exists = session_file.exists() and session_file.stat().st_size > 50

    return SystemSettingsRead(
        openrouter_api_key_set=bool(openrouter_key),
        openrouter_model=openrouter_model,
        threads_username=threads_user,
        threads_password_set=bool(threads_pass),
        threads_session_id_set=bool(threads_session_id),
        admin_passcode_set=True,
        scheduler_enabled=sched_enabled,
        scheduler_window_minutes=window_min,
        scheduler_posts_per_window=posts_count,
        calculated_interval_minutes=calc_interval,
        min_thread_comments=min_comments,
        min_thread_likes=min_likes,
        headless_browser=headless,
        proxy_url=proxy_url,
        session_file_exists=session_file_exists
    )


@router.put("", dependencies=[Depends(verify_admin)])
async def update_settings(payload: SystemSettingsUpdate, db: AsyncSession = Depends(get_db)):
    if payload.openrouter_api_key is not None:
        await set_or_update(db, "openrouter_api_key", payload.openrouter_api_key)
    if payload.openrouter_model is not None:
        await set_or_update(db, "openrouter_model", payload.openrouter_model)
    if payload.threads_username is not None:
        await set_or_update(db, "threads_username", payload.threads_username)
    if payload.threads_password is not None and payload.threads_password.strip() != "":
        await set_or_update(db, "threads_password", payload.threads_password)
    if payload.threads_session_id is not None:
        await set_or_update(db, "threads_session_id", payload.threads_session_id.strip())
    if payload.admin_passcode is not None and payload.admin_passcode.strip() != "":
        await set_or_update(db, "admin_passcode", payload.admin_passcode.strip())
    if payload.scheduler_enabled is not None:
        await set_or_update(db, "scheduler_enabled", str(payload.scheduler_enabled))
    if payload.scheduler_window_minutes is not None:
        await set_or_update(db, "scheduler_window_minutes", str(payload.scheduler_window_minutes))
    if payload.scheduler_posts_per_window is not None:
        await set_or_update(db, "scheduler_posts_per_window", str(payload.scheduler_posts_per_window))
    if payload.min_thread_comments is not None:
        await set_or_update(db, "min_thread_comments", str(payload.min_thread_comments))
    if payload.min_thread_likes is not None:
        await set_or_update(db, "min_thread_likes", str(payload.min_thread_likes))
    if payload.headless_browser is not None:
        await set_or_update(db, "headless_browser", str(payload.headless_browser))
    if payload.proxy_url is not None:
        await set_or_update(db, "proxy_url", payload.proxy_url.strip())

    await db.commit()
    # Reload cron schedule to apply interval changes immediately
    await cron_scheduler.reload_schedule()

    return {"success": True, "message": "Settings successfully saved to database"}


@router.post("/upload-session", dependencies=[Depends(verify_admin)])
async def upload_session_file(file: UploadFile = File(...)):
    """Uploads a valid threads_session.json to bypass VPS login barriers."""
    content_bytes = await file.read()
    try:
        data = json.loads(content_bytes)
        if not isinstance(data, dict) or ("cookies" not in data and "origins" not in data):
            raise ValueError("File is not a valid Playwright storage_state JSON file.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid session JSON file: {str(e)}")

    session_path = Path(settings.SESSIONS_PATH) / "threads_session.json"
    session_path.parent.mkdir(parents=True, exist_ok=True)
    session_path.write_bytes(content_bytes)
    return {
        "success": True,
        "message": "Session file uploaded successfully. The bot will immediately use this active session."
    }


@router.get("/export-session", dependencies=[Depends(verify_admin)])
async def export_session_file():
    """Downloads the current threads_session.json if it exists."""
    session_path = Path(settings.SESSIONS_PATH) / "threads_session.json"
    if not session_path.exists():
        raise HTTPException(status_code=404, detail="No active session file found")
    return FileResponse(
        str(session_path),
        media_type="application/json",
        filename="threads_session.json"
    )


@router.delete("/delete-session", dependencies=[Depends(verify_admin)])
async def delete_session_file():
    """Deletes the current threads_session.json to reset authentication."""
    session_path = Path(settings.SESSIONS_PATH) / "threads_session.json"
    if session_path.exists():
        session_path.unlink(missing_ok=True)
    return {"success": True, "message": "Session file deleted successfully"}
