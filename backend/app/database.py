from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from app.config import settings

from sqlalchemy import event
from sqlalchemy.engine import Engine

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    connect_args={"check_same_thread": False}
)

# Enable SQLite foreign keys and WAL journal mode for performance
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


from sqlalchemy import text


def migrate_sqlite_tables(conn):
    try:
        res = conn.execute(text("PRAGMA table_info(products)"))
        existing_cols = {row[1] for row in res.fetchall()}
        
        new_cols_products = [
            ("product_id", "VARCHAR(100)"),
            ("price", "VARCHAR(100)"),
            ("sales_count", "VARCHAR(100)"),
            ("shop_name", "VARCHAR(255)"),
            ("commission_rate", "VARCHAR(50)"),
            ("commission_amount", "VARCHAR(100)"),
            ("product_url", "TEXT"),
            ("extra_commission_url", "TEXT"),
            ("is_posted", "BOOLEAN DEFAULT 0"),
            ("post_count", "INTEGER DEFAULT 0"),
            ("last_posted_at", "DATETIME")
        ]
        for col_name, col_type in new_cols_products:
            if col_name not in existing_cols:
                conn.execute(text(f"ALTER TABLE products ADD COLUMN {col_name} {col_type}"))

        res_logs = conn.execute(text("PRAGMA table_info(post_logs)"))
        existing_log_cols = {row[1] for row in res_logs.fetchall()}
        new_cols_logs = [
            ("extra_commission_url", "TEXT"),
            ("target_thread_url", "VARCHAR(500)"),
            ("target_thread_snippet", "TEXT")
        ]
        for col_name, col_type in new_cols_logs:
            if col_name not in existing_log_cols:
                conn.execute(text(f"ALTER TABLE post_logs ADD COLUMN {col_name} {col_type}"))

        res_ct = conn.execute(text("PRAGMA table_info(commented_threads)"))
        existing_ct_cols = {row[1] for row in res_ct.fetchall()}
        if "like_count_found" not in existing_ct_cols:
            conn.execute(text("ALTER TABLE commented_threads ADD COLUMN like_count_found INTEGER DEFAULT 0"))
    except Exception as e:
        pass


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(migrate_sqlite_tables)
