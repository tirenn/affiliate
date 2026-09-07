from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import SchedulerStatusRead, TriggerResponse, ToggleSchedulerRequest
from app.routers.dependencies import verify_admin
from app.scheduler.cron_runner import cron_scheduler
from app.routers.settings import set_or_update

router = APIRouter(prefix="/api/cron", tags=["Scheduler"])


@router.get("/status", response_model=SchedulerStatusRead)
async def get_cron_status():
    status_data = await cron_scheduler.get_status()
    return SchedulerStatusRead(**status_data)


@router.post("/trigger-now", response_model=TriggerResponse, dependencies=[Depends(verify_admin)])
async def trigger_post_now(background_tasks: BackgroundTasks):
    if cron_scheduler.is_currently_posting:
        raise HTTPException(status_code=409, detail="Another post job is already currently running")

    # Run in background so API responds immediately (manual trigger, not cron)
    background_tasks.add_task(cron_scheduler.trigger_next_product, is_cron=False)

    return TriggerResponse(
        success=True,
        message="Posting job dispatched successfully for the next pending product in queue."
    )


@router.post("/toggle", dependencies=[Depends(verify_admin)])
async def toggle_scheduler(
    payload: Optional[ToggleSchedulerRequest] = None,
    enabled: Optional[bool] = None,
    db: AsyncSession = Depends(get_db)
):
    target_state = payload.enabled if payload is not None else enabled
    if target_state is None:
        raise HTTPException(status_code=400, detail="Parameter 'enabled' is required.")

    await set_or_update(db, "scheduler_enabled", str(target_state))
    await db.commit()
    await cron_scheduler.reload_schedule()
    status_data = await cron_scheduler.get_status()
    return {
        "success": True,
        "scheduler_enabled": target_state,
        "message": f"Cron scheduler {'enabled' if target_state else 'paused'}.",
        "cron_status": status_data
    }
