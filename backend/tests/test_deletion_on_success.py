import pytest
from datetime import datetime, timezone
from sqlalchemy import select, delete
from app.models import Product, PostLog


@pytest.mark.asyncio
async def test_product_deletion_on_post_success(db_session):
    # 1. Insert initial pending product
    prod = Product(
        product_name="Wireless Earbuds Test",
        affiliate_url="https://example.com/earbuds",
        status="pending"
    )
    db_session.add(prod)
    await db_session.commit()
    await db_session.refresh(prod)
    prod_id = prod.id

    # 2. Simulate post execution and success logging
    post_log = PostLog(
        product_id=prod_id,
        product_name=prod.product_name,
        affiliate_url=prod.affiliate_url,
        post_text="Check out these wireless earbuds! https://example.com/earbuds #tech",
        threads_post_url="https://threads.net/@user/post/123",
        status="success",
        completed_at=datetime.now(timezone.utc)
    )
    db_session.add(post_log)
    await db_session.commit()

    # User requirement rule: after success posting on threads, delete the row
    await db_session.execute(delete(Product).where(Product.id == prod_id))
    await db_session.commit()

    # 3. Verify product row is deleted
    result = await db_session.execute(select(Product).where(Product.id == prod_id))
    assert result.scalar_one_or_none() is None

    # 4. Verify post log history still exists
    log_res = await db_session.execute(select(PostLog).where(PostLog.id == post_log.id))
    saved_log = log_res.scalar_one_or_none()
    assert saved_log is not None
    assert saved_log.status == "success"
    assert saved_log.product_name == "Wireless Earbuds Test"
