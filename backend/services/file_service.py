"""文件查询服务层"""
import os
from backend.models import database as db
from backend.config import get_file_type, FILE_TYPE_LABELS, TOP_ITEMS_LIMIT


async def get_tree(scan_id: int, path: str = None, sort_by: str = "size",
                   order: str = "desc", include_files: bool = True) -> dict:
    """获取目录树"""
    database = await db.get_db()

    # 获取扫描信息
    scan = await db.get_scan(database, scan_id)
    if not scan:
        return None

    root_path = scan["root_path"]
    current_path = path or root_path

    # 获取当前目录信息
    dir_info = await db.get_directory_info(database, scan_id, current_path)
    current_size = dir_info["total_size"] if dir_info else 0

    # 获取子项
    items = await db.get_tree_items(
        database, scan_id, current_path,
        sort_by=sort_by, order=order,
        include_files=include_files, limit=TOP_ITEMS_LIMIT
    )

    # 计算百分比
    for item in items:
        if current_size > 0:
            item["size_percent"] = round(item.get("size", 0) / current_size * 100, 1)
        else:
            item["size_percent"] = 0

    # 构建面包屑
    breadcrumb = _build_breadcrumb(current_path, root_path)

    # 统计信息
    total_dirs = sum(1 for i in items if i.get("is_dir") and not i.get("is_others"))
    total_files = sum(1 for i in items if not i.get("is_dir") and not i.get("is_others"))

    return {
        "scan_id": scan_id,
        "parent_path": os.path.dirname(current_path),
        "current_path": current_path,
        "current_size": current_size,
        "breadcrumb": breadcrumb,
        "items": items,
        "summary": {
            "total_items": len(items),
            "total_dirs": total_dirs,
            "total_files": total_files,
        },
    }


def _build_breadcrumb(current_path: str, root_path: str) -> list[dict]:
    """构建面包屑导航"""
    breadcrumb = []
    path = current_path

    # 从当前路径向上构建到根路径
    parts = []
    while True:
        parts.append({"name": os.path.basename(path) or path, "path": path})
        parent = os.path.dirname(path)
        if parent == path or path == root_path:
            break
        path = parent

    parts.reverse()

    # 确保根路径在最前面
    if not parts or parts[0]["path"] != root_path:
        parts.insert(0, {"name": os.path.basename(root_path) or root_path, "path": root_path})

    return parts


async def get_top_files(scan_id: int, limit: int = 50, offset: int = 0,
                        extension: str = None, sort_by: str = "size",
                        order: str = "desc") -> dict:
    """获取大文件排行"""
    database = await db.get_db()
    result = await db.get_top_files(
        database, scan_id, limit=limit, offset=offset,
        extension=extension, sort_by=sort_by, order=order
    )

    # 补充 parent_dir
    for item in result["items"]:
        item["parent_dir"] = os.path.dirname(item["path"])

    return result


async def get_file_types(scan_id: int) -> dict:
    """获取文件类型统计"""
    database = await db.get_db()
    rows = await db.get_file_types(database, scan_id)

    categories = []
    top_extensions = []
    total_size = 0

    for row in rows:
        ext = row["extension"]
        file_type = get_file_type(ext)
        label = FILE_TYPE_LABELS.get(file_type, "其他文件")
        if not ext:
            ext = "(无扩展名)"

        categories.append({
            "extension": ext,
            "label": label,
            "file_count": row["file_count"],
            "total_size": row["total_size"],
            "size_percent": row["size_percent"],
        })

        if row["extension"]:
            top_extensions.append(row["extension"])
        total_size += row["total_size"]

    return {
        "categories": categories[:30],  # 最多返回 30 个类型
        "top_extensions": top_extensions[:10],
        "total_size": total_size,
    }
