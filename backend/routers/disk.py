"""磁盘分区 API"""
import psutil
from pathlib import Path
from fastapi import APIRouter
from backend.models.schemas import ApiResponse

router = APIRouter(prefix="/api", tags=["disks"])


@router.get("/disks")
async def get_disks():
    """获取磁盘分区信息"""
    partitions = []
    for part in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(part.mountpoint)
            partitions.append({
                "letter": part.device.rstrip("\\"),
                "label": part.mountpoint,
                "total_space": usage.total,
                "used_space": usage.used,
                "free_space": usage.free,
                "usage_percent": round(usage.percent, 1),
                "fs_type": part.fstype,
                "mount_point": part.mountpoint,
            })
        except (PermissionError, OSError):
            continue

    return {"code": 200, "data": {"partitions": partitions}}


@router.get("/common-paths")
async def get_common_paths():
    """获取常用目录路径"""
    home = Path.home()
    project_root = Path(__file__).resolve().parents[2]
    candidates = [
        {"name": "项目目录", "path": str(project_root)},
        {"name": "用户目录", "path": str(home)},
        {"name": "桌面", "path": str(home / "Desktop")},
        {"name": "下载", "path": str(home / "Downloads")},
        {"name": "文档", "path": str(home / "Documents")},
        {"name": "图片", "path": str(home / "Pictures")},
        {"name": "视频", "path": str(home / "Videos")},
        {"name": "音乐", "path": str(home / "Music")},
    ]
    for part in psutil.disk_partitions(all=False):
        letter = part.mountpoint.rstrip("\\")
        candidates.append({"name": f"磁盘 {letter}", "path": part.mountpoint})

    results = []
    for c in candidates:
        p = Path(c["path"])
        results.append({"name": c["name"], "path": c["path"], "exists": p.exists() and p.is_dir()})

    return {"code": 200, "data": {"paths": results}}
