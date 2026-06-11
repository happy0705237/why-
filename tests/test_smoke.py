"""最小后端 smoke test — 覆盖 V1.0 全部 API 端点

运行方式:
    pip install -r requirements.txt
    pytest tests/test_smoke.py -v
"""
import os
import sys
import time
import pytest
import pytest_asyncio

# 确保项目根目录在 sys.path 中
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# 每次测试使用内存数据库
os.environ["DISKMANAGER_DB"] = ":memory:"

from httpx import AsyncClient, ASGITransport
from backend.server import app
from backend.models import database as db


@pytest_asyncio.fixture(autouse=True)
async def _reset_db():
    """每个测试前重置数据库连接，保证干净状态"""
    await db.close_db()
    yield
    await db.close_db()


# ── 1. 磁盘分区 ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_disks():
    """GET /api/disks 返回真实分区列表"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/disks")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 200
    partitions = body["data"]["partitions"]
    assert isinstance(partitions, list)
    assert len(partitions) >= 1
    p = partitions[0]
    for key in ("letter", "total_space", "used_space", "free_space", "usage_percent"):
        assert key in p, f"缺少字段 {key}"


# ── 2. 扫描完整流程 ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_scan_full_flow():
    """POST /api/scan → 轮询 → tree → files/top → files/types"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        scan_path = os.path.join(ROOT, "backend")
        resp = await client.post("/api/scan", json={"path": scan_path})
        assert resp.status_code == 201
        scan_id = resp.json()["data"]["scan_id"]

        # 轮询等待完成
        for _ in range(30):
            resp = await client.get(f"/api/scan/{scan_id}")
            assert resp.status_code == 200
            status = resp.json()["data"]["status"]
            if status in ("completed", "failed"):
                break
            time.sleep(0.5)

        scan_data = resp.json()["data"]
        assert scan_data["status"] == "completed", f"扫描状态: {scan_data['status']}"
        assert scan_data["file_count"] > 0
        assert scan_data["total_size"] > 0

        # 目录树
        resp = await client.get(f"/api/scan/{scan_id}/tree")
        assert resp.status_code == 200
        tree = resp.json()["data"]
        assert len(tree["items"]) > 0
        assert len(tree["breadcrumb"]) >= 1

        # 大文件排行
        resp = await client.get(f"/api/scan/{scan_id}/files/top?limit=5")
        assert resp.status_code == 200
        top = resp.json()["data"]
        assert top["total"] > 0
        assert len(top["items"]) <= 5

        # 文件类型统计
        resp = await client.get(f"/api/scan/{scan_id}/files/types")
        assert resp.status_code == 200
        types = resp.json()["data"]
        assert types["total_size"] > 0
        assert len(types["categories"]) >= 1


# ── 3. 扫描错误路径 ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_scan_nonexistent_path():
    """POST /api/scan 路径不存在应返回 400"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/scan", json={"path": "Z:\\does_not_exist_12345"})
    assert resp.status_code == 400


# ── 4. 扫描不存在的 ID ──────────────────────────────────────

@pytest.mark.asyncio
async def test_scan_not_found():
    """GET /api/scan/99999 应返回 404"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/scan/99999")
    assert resp.status_code == 404


# ── 5. 扫描历史列表 ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_scans_list():
    """GET /api/scans 返回分页结构"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/scans")
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert "total" in body
    assert "items" in body
    assert isinstance(body["items"], list)


# ── 6. 首页可访问 ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_index_page():
    """GET / 返回 HTML"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/")
    assert resp.status_code == 200
    assert "DiskManager" in resp.text


# ── 7. open-explorer 端点 ────────────────────────────────────

@pytest.mark.asyncio
async def test_open_explorer():
    """POST /api/open-explorer 路径不存在应返回 code=404"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/open-explorer", json={"path": "Z:\\no_such_path"})
    assert resp.status_code == 200
    assert resp.json()["code"] == 404


# ── 8. 扫描错误详情 ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_scan_errors():
    """GET /api/scan/{id}/errors 返回分页结构"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 先跑一次扫描
        scan_path = os.path.join(ROOT, "backend")
        resp = await client.post("/api/scan", json={"path": scan_path})
        scan_id = resp.json()["data"]["scan_id"]
        for _ in range(30):
            resp = await client.get(f"/api/scan/{scan_id}")
            if resp.json()["data"]["status"] in ("completed", "failed"):
                break
            time.sleep(0.5)

        # 查询错误
        resp = await client.get(f"/api/scan/{scan_id}/errors")
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert "total" in body
    assert "by_type" in body
    assert "items" in body
    assert isinstance(body["items"], list)


# ── 9. 常用路径 ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_common_paths():
    """GET /api/common-paths 返回常用路径列表"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/common-paths")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 200
    paths = body["data"]["paths"]
    assert isinstance(paths, list)
    assert len(paths) >= 1
    for p in paths:
        assert "name" in p
        assert "path" in p
        assert "exists" in p
    assert any(p["exists"] for p in paths)
    project_paths = [p for p in paths if p["name"] == "项目目录"]
    assert project_paths, "缺少项目目录快捷项"
    assert project_paths[0]["path"] == ROOT
    assert project_paths[0]["exists"] is True


# ── 10. 删除扫描记录 ───────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_scan_flow():
    """DELETE /api/scan/{id} 删除已完成的扫描记录"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        scan_path = os.path.join(ROOT, "backend")
        resp = await client.post("/api/scan", json={"path": scan_path})
        scan_id = resp.json()["data"]["scan_id"]

        for _ in range(30):
            resp = await client.get(f"/api/scan/{scan_id}")
            if resp.json()["data"]["status"] in ("completed", "failed"):
                break
            time.sleep(0.5)

        resp = await client.delete(f"/api/scan/{scan_id}")
        assert resp.status_code == 200
        assert resp.json()["code"] == 200

        resp = await client.get(f"/api/scan/{scan_id}")
        assert resp.status_code == 404

        resp = await client.delete(f"/api/scan/{scan_id}")
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_running_scan_conflict():
    """DELETE /api/scan/{id} 不应删除 scanning 状态的记录"""
    database = await db.get_db()
    scan_id = await db.create_scan(database, ROOT)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.delete(f"/api/scan/{scan_id}")
        assert resp.status_code == 409

        resp = await client.get(f"/api/scan/{scan_id}")
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "scanning"
