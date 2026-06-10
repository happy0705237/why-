"""扫描任务 API"""
from fastapi import APIRouter, HTTPException
from backend.models.schemas import ScanRequest
from backend.services import scan_service
from backend.models import database as db

router = APIRouter(prefix="/api", tags=["scan"])


@router.post("/scan", status_code=201)
async def create_scan(req: ScanRequest):
    """创建扫描任务"""
    result = await scan_service.create_scan(
        root_path=req.path,
        max_depth=req.max_depth,
        exclude_paths=req.exclude_paths,
        exclude_extensions=req.exclude_extensions,
        min_file_size=req.min_file_size,
    )

    if "error" in result:
        code = result.get("code", 400)
        raise HTTPException(status_code=code, detail=result["error"])

    return {"code": 201, "data": result}


@router.get("/scan/{scan_id}")
async def get_scan(scan_id: int):
    """获取扫描任务状态"""
    result = await scan_service.get_scan_status(scan_id)
    if not result:
        raise HTTPException(status_code=404, detail="扫描任务不存在")
    return {"code": 200, "data": result}


@router.delete("/scan/{scan_id}")
async def cancel_scan(scan_id: int):
    """取消/删除扫描任务"""
    # 先尝试取消正在运行的任务
    cancelled = await scan_service.cancel_scan(scan_id)
    if cancelled:
        return {"code": 200, "message": "扫描任务已取消"}

    # 检查任务是否存在
    database = await db.get_db()
    scan = await db.get_scan(database, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="扫描任务不存在")

    return {"code": 200, "message": "扫描任务已完成"}


@router.get("/scans")
async def list_scans(page: int = 1, page_size: int = 20):
    """获取扫描历史列表"""
    database = await db.get_db()
    result = await db.get_scans(database, page=page, page_size=page_size)
    return {"code": 200, "data": result}


@router.get("/scan/{scan_id}/tree")
async def get_tree(scan_id: int, path: str = None, sort_by: str = "size",
                   order: str = "desc", include_files: bool = True):
    """获取目录树"""
    result = await scan_service.get_scan_status(scan_id)
    if not result:
        raise HTTPException(status_code=404, detail="扫描任务不存在")

    from backend.services.file_service import get_tree
    tree = await get_tree(scan_id, path, sort_by, order, include_files)
    if not tree:
        raise HTTPException(status_code=404, detail="目录数据不存在")

    return {"code": 200, "data": tree}


@router.get("/scan/{scan_id}/errors")
async def get_scan_errors(scan_id: int, limit: int = 50, offset: int = 0):
    """获取扫描错误详情"""
    database = await db.get_db()
    scan = await db.get_scan(database, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="扫描任务不存在")

    result = await db.get_scan_errors(database, scan_id, limit=limit, offset=offset)
    return {"code": 200, "data": result}
