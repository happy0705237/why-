"""文件查询 API"""
from fastapi import APIRouter, HTTPException
from backend.services import file_service
from backend.models import database as db

router = APIRouter(prefix="/api/scan/{scan_id}/files", tags=["files"])


@router.get("/top")
async def get_top_files(scan_id: int, limit: int = 50, offset: int = 0,
                        extension: str = None, sort_by: str = "size",
                        order: str = "desc"):
    """大文件排行"""
    # 验证扫描存在
    database = await db.get_db()
    scan = await db.get_scan(database, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="扫描任务不存在")

    result = await file_service.get_top_files(
        scan_id, limit=limit, offset=offset,
        extension=extension, sort_by=sort_by, order=order
    )
    return {"code": 200, "data": result}


@router.get("/types")
async def get_file_types(scan_id: int):
    """按文件类型统计"""
    database = await db.get_db()
    scan = await db.get_scan(database, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="扫描任务不存在")

    result = await file_service.get_file_types(scan_id)
    return {"code": 200, "data": result}
