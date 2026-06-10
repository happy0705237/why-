"""扫描服务层"""
import asyncio
from pathlib import Path
from backend.models import database as db
from backend.core.scanner import run_scan

# 当前运行的扫描任务
_running_scans: dict[int, asyncio.Task] = {}


async def create_scan(root_path: str, max_depth: int = None,
                      exclude_paths: list[str] = None,
                      exclude_extensions: list[str] = None,
                      min_file_size: int = 0) -> dict:
    """创建扫描任务"""
    # 检查路径是否存在
    path = Path(root_path)
    if not path.exists():
        return {"error": "路径不存在", "code": 400}
    if not path.is_dir():
        return {"error": "路径不是目录", "code": 400}

    # 检查是否有正在运行的扫描
    for scan_id, task in _running_scans.items():
        if not task.done():
            database = await db.get_db()
            scan_info = await db.get_scan(database, scan_id)
            if scan_info:
                return {
                    "error": "已有扫描任务正在运行",
                    "code": 409,
                    "running_scan_id": scan_id,
                    "running_scan_path": scan_info["root_path"],
                }

    # 创建扫描记录
    database = await db.get_db()
    scan_id = await db.create_scan(database, root_path)

    # 启动异步扫描任务
    task = asyncio.create_task(
        run_scan(scan_id, root_path, max_depth, exclude_paths, exclude_extensions, min_file_size)
    )
    _running_scans[scan_id] = task

    # 扫描完成后清理
    task.add_done_callback(lambda t: _running_scans.pop(scan_id, None))

    return {"scan_id": scan_id, "status": "scanning", "message": "扫描任务已启动"}


async def get_scan_status(scan_id: int) -> dict | None:
    """获取扫描状态"""
    database = await db.get_db()
    scan = await db.get_scan(database, scan_id)
    if not scan:
        return None

    # 获取进度信息（扫描中和完成后都返回，前端轮询依赖此字段）
    progress = {}
    if scan["status"] == "scanning":
        prog = await db.get_scan_progress(database, scan_id)
        current_path = await db.get_current_path(database, scan_id)
        progress = {
            "scanned_files": prog["file_count"],
            "scanned_dirs": prog["dir_count"],
            "current_path": current_path,
        }

    return {
        "id": scan["id"],
        "root_path": scan["root_path"],
        "status": scan["status"],
        "total_size": scan["total_size"],
        "file_count": scan["file_count"],
        "dir_count": scan["dir_count"],
        "error_count": scan["error_count"],
        "scan_duration": scan["scan_duration"],
        "started_at": scan["started_at"],
        "completed_at": scan["completed_at"],
        "progress": progress,
    }


async def cancel_scan(scan_id: int) -> bool:
    """取消扫描任务"""
    task = _running_scans.get(scan_id)
    if task and not task.done():
        task.cancel()
        database = await db.get_db()
        await db.update_scan_status(database, scan_id, "cancelled")
        return True
    return False
