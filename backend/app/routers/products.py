import csv
import io
from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.database import get_db
from app.models import Product
from app.schemas import ProductRead, CSVUploadResponse, BulkDeleteRequest
from app.routers.dependencies import verify_admin

router = APIRouter(prefix="/api/products", tags=["Products"])


def detect_delimiter(sample_text: str) -> str:
    """Detect if CSV is tab-separated or comma-separated or semicolon-separated"""
    first_line = sample_text.splitlines()[0] if sample_text.splitlines() else ""
    if "\t" in first_line:
        return "\t"
    elif ";" in first_line and first_line.count(";") > first_line.count(","):
        return ";"
    return ","


@router.post("/upload-csv", response_model=CSVUploadResponse, dependencies=[Depends(verify_admin)])
async def upload_csv(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    content_bytes = await file.read()
    # Decode safely with utf-8-sig to strip BOM if present
    try:
        content_text = content_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        content_text = content_bytes.decode("latin-1", errors="replace")

    content_clean = content_text.strip()
    if not content_clean:
        raise HTTPException(status_code=400, detail="File CSV kosong")

    delim = detect_delimiter(content_clean)
    csv_file = io.StringIO(content_clean)
    reader = csv.reader(csv_file, delimiter=delim)
    rows = list(reader)

    if not rows or len(rows) < 2:
        raise HTTPException(status_code=400, detail="File CSV harus memiliki minimal 1 baris header dan 1 baris data")

    headers = [h.strip().lower() for h in rows[0]]
    data_rows = rows[1:]

    # Helper function to find column index by candidate names
    def find_col(candidates, exact=False):
        for idx, h in enumerate(headers):
            for c in candidates:
                if h == c:
                    return idx
        if not exact:
            for idx, h in enumerate(headers):
                for c in candidates:
                    if c in h:
                        return idx
        return -1

    id_idx = find_col(["id produk", "product id", "id_produk", "item id", "id"])
    name_idx = find_col(["nama produk", "product name", "nama", "title"])
    price_idx = find_col(["harga", "price"])
    sales_idx = find_col(["penjualan", "terjual", "sold", "sales"])
    shop_idx = find_col(["nama toko", "toko", "shop name", "store"])
    comm_rate_idx = find_col(["komisi hingga", "komisi rate", "rate komisi", "komisi %"])
    comm_amount_idx = find_col(["komisi"], exact=True)
    if comm_amount_idx == -1:
        for idx, h in enumerate(headers):
            if h == "komisi":
                comm_amount_idx = idx
                break
    prod_url_idx = find_col(["link produk", "product link", "product url", "url produk"])
    extra_comm_idx = find_col(["link komisi ekstra", "komisi ekstra", "extra commission", "link ekstra"])

    if name_idx == -1 and len(headers) >= 2:
        name_idx = 1
    if extra_comm_idx == -1:
        extra_comm_idx = find_col(["link", "url", "affiliate"])

    added = 0
    skipped_duplicates = 0
    failed = 0

    # Cache existing product_ids to optimize deduplication check
    existing_result = await db.execute(select(Product.product_id).where(Product.product_id.isnot(None)))
    existing_ids = set(existing_result.scalars().all())

    for row in data_rows:
        if not row or not any(cell.strip() for cell in row):
            continue

        def get_val(idx):
            return row[idx].strip() if idx != -1 and idx < len(row) else None

        prod_id = get_val(id_idx)
        name = get_val(name_idx)
        extra_link = get_val(extra_comm_idx)
        prod_link = get_val(prod_url_idx)

        # The primary link to use for posting is Link Komisi Ekstra, fallback to Link Produk
        final_affiliate_url = extra_link or prod_link

        if not name or not final_affiliate_url:
            failed += 1
            continue

        # Check duplicate by product_id
        if prod_id and prod_id in existing_ids:
            skipped_duplicates += 1
            continue

        product = Product(
            product_id=prod_id,
            product_name=name,
            price=get_val(price_idx),
            sales_count=get_val(sales_idx),
            shop_name=get_val(shop_idx),
            commission_rate=get_val(comm_rate_idx),
            commission_amount=get_val(comm_amount_idx),
            product_url=prod_link,
            extra_commission_url=extra_link,
            affiliate_url=final_affiliate_url,
            is_posted=False,
            post_count=0,
            status="pending"
        )
        db.add(product)
        if prod_id:
            existing_ids.add(prod_id)
        added += 1

    await db.commit()

    return CSVUploadResponse(
        total_parsed=len(data_rows),
        added=added,
        skipped_duplicates=skipped_duplicates,
        failed=failed,
        message=f"Berhasil mengimpor {added} produk. {skipped_duplicates} duplikat diabaikan."
    )


@router.get("", response_model=List[ProductRead], dependencies=[Depends(verify_admin)])
async def list_products(
    is_posted: Optional[bool] = None,
    search: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Product).order_by(Product.id.asc()).offset(offset).limit(limit)
    if is_posted is not None:
        stmt = stmt.where(Product.is_posted == is_posted)
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(
            (Product.product_name.ilike(pattern)) |
            (Product.shop_name.ilike(pattern)) |
            (Product.product_id.ilike(pattern))
        )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.delete("/{product_id}", dependencies=[Depends(verify_admin)])
async def delete_product(product_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Produk tidak ditemukan")

    await db.execute(delete(Product).where(Product.id == product_id))
    await db.commit()
    return {"success": True, "message": f"Produk #{product_id} berhasil dihapus"}


@router.post("/bulk-delete", dependencies=[Depends(verify_admin)])
async def bulk_delete_products(payload: BulkDeleteRequest, db: AsyncSession = Depends(get_db)):
    if not payload.product_ids:
        return {"success": True, "deleted_count": 0}

    stmt = delete(Product).where(Product.id.in_(payload.product_ids))
    result = await db.execute(stmt)
    await db.commit()
    return {
        "success": True,
        "deleted_count": result.rowcount,
        "message": f"Berhasil menghapus {result.rowcount} produk terpilih"
    }


@router.post("/delete-all", dependencies=[Depends(verify_admin)])
async def delete_all_products(db: AsyncSession = Depends(get_db)):
    result = await db.execute(delete(Product))
    await db.commit()
    return {
        "success": True,
        "deleted_count": result.rowcount,
        "message": "Semua produk berhasil dihapus dari database"
    }


@router.post("/{product_id}/retry", dependencies=[Depends(verify_admin)])
async def retry_product(product_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Produk tidak ditemukan")

    product.status = "pending"
    product.is_posted = False
    product.last_error = None
    await db.commit()
    return {"success": True, "message": f"Produk #{product_id} di-reset ke antrean belum terpost"}
