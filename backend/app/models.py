from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index, Boolean
from sqlalchemy.orm import relationship
from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(String(100), unique=True, index=True, nullable=True)  # ID Produk dari Shopee
    product_name = Column(String(500), nullable=False, index=True)
    price = Column(String(100), nullable=True)  # e.g. "20,6RB"
    sales_count = Column(String(100), nullable=True)  # e.g. "10RB+"
    shop_name = Column(String(255), nullable=True)  # e.g. "Melany Collection"
    commission_rate = Column(String(50), nullable=True)  # e.g. "14,5%"
    commission_amount = Column(String(100), nullable=True)  # e.g. "Rp2.881"
    product_url = Column(Text, nullable=True)  # Link Produk
    extra_commission_url = Column(Text, nullable=True)  # Link Komisi Ekstra (Utama)
    affiliate_url = Column(Text, nullable=False)  # Fallback link
    
    is_posted = Column(Boolean, default=False, index=True)  # True jika sudah terpost di siklus saat ini
    post_count = Column(Integer, default=0)  # Total berapa kali pernah dipost
    last_posted_at = Column(DateTime, nullable=True)
    
    status = Column(String(50), default="pending", index=True)  # pending, in_progress, posted, failed
    retry_count = Column(Integer, default=0)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    post_logs = relationship("PostLog", back_populates="product", cascade="all, delete-orphan")


class CommentedThread(Base):
    """Mencatat thread viral yang sudah pernah dikomentari agar tidak terjadi spam komentar"""
    __tablename__ = "commented_threads"

    id = Column(Integer, primary_key=True, index=True)
    thread_url = Column(String(500), unique=True, index=True, nullable=False)
    thread_author = Column(String(255), nullable=True)
    thread_snippet = Column(Text, nullable=True)
    comment_count_found = Column(Integer, default=0)
    like_count_found = Column(Integer, default=0)
    created_at = Column(DateTime, default=utc_now, index=True)


class PostLog(Base):
    __tablename__ = "post_logs"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    product_name = Column(String(500), nullable=False)
    affiliate_url = Column(Text, nullable=False)
    extra_commission_url = Column(Text, nullable=True)
    
    target_thread_url = Column(String(500), nullable=True)
    target_thread_snippet = Column(Text, nullable=True)
    post_text = Column(Text, nullable=True)
    threads_post_url = Column(String(500), nullable=True)
    threads_post_id = Column(String(255), nullable=True)
    status = Column(String(50), default="running", index=True)  # running, success, failed
    error_message = Column(Text, nullable=True)
    final_screenshot = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now, index=True)
    completed_at = Column(DateTime, nullable=True)

    product = relationship("Product", back_populates="post_logs")
    steps = relationship("AgentStepLog", back_populates="post_log", cascade="all, delete-orphan", order_by="AgentStepLog.step_number")


class AgentStepLog(Base):
    __tablename__ = "agent_step_logs"

    id = Column(Integer, primary_key=True, index=True)
    post_log_id = Column(Integer, ForeignKey("post_logs.id", ondelete="CASCADE"), nullable=False, index=True)
    step_number = Column(Integer, nullable=False)
    tool_name = Column(String(100), nullable=False)
    tool_arguments = Column(Text, nullable=True)
    tool_output = Column(Text, nullable=True)
    thought = Column(Text, nullable=True)
    screenshot_path = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now)

    post_log = relationship("PostLog", back_populates="steps")


class SystemSetting(Base):
    __tablename__ = "system_settings"

    key = Column(String(100), primary_key=True, index=True)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
