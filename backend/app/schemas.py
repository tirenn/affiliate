from datetime import datetime
from typing import Optional, List, Any, Dict
from pydantic import BaseModel, Field, ConfigDict


class ProductBase(BaseModel):
    product_name: str
    affiliate_url: str
    extra_commission_url: Optional[str] = None
    product_url: Optional[str] = None
    product_id: Optional[str] = None
    price: Optional[str] = None
    sales_count: Optional[str] = None
    shop_name: Optional[str] = None
    commission_rate: Optional[str] = None
    commission_amount: Optional[str] = None


class ProductCreate(ProductBase):
    pass


class ProductRead(ProductBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    is_posted: bool = False
    post_count: int = 0
    last_posted_at: Optional[datetime] = None
    retry_count: int
    last_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class BulkDeleteRequest(BaseModel):
    product_ids: List[int]


class CSVUploadResponse(BaseModel):
    total_parsed: int
    added: int
    skipped_duplicates: int
    failed: int
    message: str


class AgentStepLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    step_number: int
    tool_name: str
    tool_arguments: Optional[str] = None
    tool_output: Optional[str] = None
    thought: Optional[str] = None
    screenshot_path: Optional[str] = None
    created_at: datetime


class PostLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: Optional[int] = None
    product_name: str
    affiliate_url: str
    extra_commission_url: Optional[str] = None
    target_thread_url: Optional[str] = None
    target_thread_snippet: Optional[str] = None
    post_text: Optional[str] = None
    threads_post_url: Optional[str] = None
    threads_post_id: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    final_screenshot: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


class PostLogDetailRead(PostLogRead):
    steps: List[AgentStepLogRead] = []


class SystemSettingsRead(BaseModel):
    openrouter_api_key_set: bool
    openrouter_model: str
    threads_username: str
    threads_password_set: bool
    admin_passcode_set: bool = True
    scheduler_enabled: bool
    scheduler_window_minutes: int
    scheduler_posts_per_window: int
    calculated_interval_minutes: float
    min_thread_comments: int
    min_thread_likes: int
    headless_browser: bool


class SystemSettingsUpdate(BaseModel):
    openrouter_api_key: Optional[str] = None
    openrouter_model: Optional[str] = None
    threads_username: Optional[str] = None
    threads_password: Optional[str] = None
    admin_passcode: Optional[str] = None
    scheduler_enabled: Optional[bool] = None
    scheduler_window_minutes: Optional[int] = None
    scheduler_posts_per_window: Optional[int] = None
    min_thread_comments: Optional[int] = None
    min_thread_likes: Optional[int] = None
    headless_browser: Optional[bool] = None


class ToggleSchedulerRequest(BaseModel):
    enabled: bool


class SchedulerStatusRead(BaseModel):
    is_running: bool
    scheduler_enabled: bool
    interval_minutes: float
    window_minutes: int
    posts_per_window: int
    next_run_time: Optional[datetime] = None
    total_products_count: int
    unposted_products_count: int
    commented_threads_count: int
    is_currently_posting: bool


class TriggerResponse(BaseModel):
    success: bool
    message: str
    product_id: Optional[int] = None
    post_log_id: Optional[int] = None
