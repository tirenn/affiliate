import pytest
import io
from app.config import settings


@pytest.mark.asyncio
async def test_health_check(client):
    response = await client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "SQLite"


@pytest.mark.asyncio
async def test_shopee_csv_upload_and_deduplication(client):
    headers = {"x-admin-key": settings.ADMIN_PASSCODE}

    # Tab-delimited Shopee CSV
    shopee_tsv = (
        "ID Produk\tNama Produk\tHarga\tPenjualan\tNama Toko\tKomisi hingga\tKomisi\tLink Produk\tLink Komisi Ekstra\n"
        "23787356455\tROK SPAN KNIT Bodycon Bawahan Cantik\t20,6RB\t10RB+\tMelany Collection\t14,5%\tRp2.881\thttps://shopee.co.id/product/1128864169/23787356455\thttps://s.shopee.co.id/9AOPhsQ4hS\n"
        "2358060466\tBASO ACI RAOS GARUT EXTRA PEDAAS\t5,5RB\t10RB+\tSNACK MART\t11,5%\tRp603\thttps://shopee.co.id/product/157850583/2358060466\thttps://s.shopee.co.id/904zVZQi2R\n"
    )
    files = {"file": ("shopee.csv", io.BytesIO(shopee_tsv.encode("utf-8")), "text/csv")}

    # 1. First upload: 2 products should be added
    resp1 = await client.post("/api/products/upload-csv", files=files, headers=headers)
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["added"] == 2
    assert data1["skipped_duplicates"] == 0

    # 2. Second upload with same content: duplicates should be skipped!
    files2 = {"file": ("shopee.csv", io.BytesIO(shopee_tsv.encode("utf-8")), "text/csv")}
    resp2 = await client.post("/api/products/upload-csv", files=files2, headers=headers)
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["added"] == 0
    assert data2["skipped_duplicates"] == 2

    # 3. Verify products in DB have correct extra commission links
    list_resp = await client.get("/api/products", headers=headers)
    assert list_resp.status_code == 200
    products = list_resp.json()
    assert len(products) == 2
    assert products[0]["product_id"] == "23787356455"
    assert products[0]["extra_commission_url"] == "https://s.shopee.co.id/9AOPhsQ4hS"
    assert products[0]["is_posted"] is False


@pytest.mark.asyncio
async def test_bulk_delete_and_delete_all(client):
    headers = {"x-admin-key": settings.ADMIN_PASSCODE}

    # Upload test data
    csv_data = (
        "ID Produk\tNama Produk\tLink Komisi Ekstra\n"
        "101\tItem 1\thttps://s.shopee.co.id/item1\n"
        "102\tItem 2\thttps://s.shopee.co.id/item2\n"
        "103\tItem 3\thttps://s.shopee.co.id/item3\n"
    )
    files = {"file": ("test.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")}
    await client.post("/api/products/upload-csv", files=files, headers=headers)

    prods = (await client.get("/api/products", headers=headers)).json()
    assert len(prods) == 3

    # Bulk delete 2 items
    ids_to_delete = [prods[0]["id"], prods[1]["id"]]
    del_resp = await client.post("/api/products/bulk-delete", json={"product_ids": ids_to_delete}, headers=headers)
    assert del_resp.status_code == 200
    assert del_resp.json()["deleted_count"] == 2

    prods_after = (await client.get("/api/products", headers=headers)).json()
    assert len(prods_after) == 1

    # Delete all
    all_resp = await client.post("/api/products/delete-all", headers=headers)
    assert all_resp.status_code == 200
    assert all_resp.json()["deleted_count"] == 1

    prods_empty = (await client.get("/api/products", headers=headers)).json()
    assert len(prods_empty) == 0
