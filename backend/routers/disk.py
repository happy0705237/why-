"""磁盘分区 API"""
import psutil
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
