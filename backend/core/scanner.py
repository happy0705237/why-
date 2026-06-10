"""扫描引擎 - 递归遍历目录，分批写入数据库并周期更新进度"""
import os
import time
import asyncio
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from backend import config
from backend.models import database as db

_executor = ThreadPoolExecutor(max_workers=config.MAX_WORKERS)


def _format_time(timestamp: float) -> str:
    try:
        return datetime.fromtimestamp(timestamp).isoformat()
    except (ValueError, OSError):
        return None


def _scan_directory_sync(root_path: str, max_depth: int,
                         exclude_paths: set, exclude_extensions: set,
                         min_file_size: int, batch_size: int):
    """
    同步扫描目录（生成器）。

    每积累 batch_size 条文件记录就 yield 一次：
        ("batch", file_batch, errors, scanned_files, scanned_dirs)

    扫描结束后 yield 最终结果：
        ("done", dir_sizes, total_scanned_files, total_scanned_dirs, total_errors)

    dir_sizes 在内存中自底向上累加后才返回，保证目录大小准确。
    """
    dir_sizes: dict[str, dict] = {}          # path -> {size, file_count, dir_count}
    file_batch: list[dict] = []
    errors: list[dict] = []
    scanned_files = 0
    scanned_dirs = 0
    total_errors = 0

    stack = [(root_path, "", 0)]

    def _flush():
        nonlocal file_batch, errors
        batch = file_batch
        errs = errors
        file_batch = []
        errors = []
        return batch, errs

    while stack:
        current_path, parent_path, depth = stack.pop()

        if depth > max_depth:
            continue
        if current_path in exclude_paths:
            continue

        if current_path not in dir_sizes:
            dir_sizes[current_path] = {"size": 0, "file_count": 0, "dir_count": 0}

        try:
            entries = list(os.scandir(current_path))
        except PermissionError as e:
            total_errors += 1
            errors.append({"path": current_path, "error_type": "permission",
                           "error_message": str(e)})
            if len(errors) >= batch_size:
                yield ("batch", *_flush(), scanned_files, scanned_dirs)
            continue
        except OSError as e:
            total_errors += 1
            errors.append({"path": current_path, "error_type": "os_error",
                           "error_message": str(e)})
            if len(errors) >= batch_size:
                yield ("batch", *_flush(), scanned_files, scanned_dirs)
            continue

        for entry in entries:
            try:
                entry_path = entry.path
                if entry_path in exclude_paths:
                    continue

                if entry.is_dir(follow_symlinks=False):
                    scanned_dirs += 1
                    dir_sizes[current_path]["dir_count"] += 1
                    if entry_path not in dir_sizes:
                        dir_sizes[entry_path] = {"size": 0, "file_count": 0, "dir_count": 0}
                    if depth + 1 <= max_depth:
                        stack.append((entry_path, current_path, depth + 1))

                elif entry.is_file(follow_symlinks=False):
                    ext = os.path.splitext(entry.name)[1].lstrip(".").lower()
                    if ext in exclude_extensions:
                        continue

                    try:
                        stat = entry.stat(follow_symlinks=False)
                    except OSError as e:
                        total_errors += 1
                        errors.append({"path": entry_path, "error_type": "os_error",
                                       "error_message": str(e)})
                        continue

                    file_size = stat.st_size
                    if file_size < min_file_size:
                        continue

                    scanned_files += 1
                    dir_sizes[current_path]["size"] += file_size
                    dir_sizes[current_path]["file_count"] += 1

                    file_batch.append({
                        "path": entry_path,
                        "name": entry.name,
                        "extension": ext if ext else None,
                        "size": file_size,
                        "is_dir": 0,
                        "modified_at": _format_time(stat.st_mtime),
                        "parent_path": current_path,
                        "depth": depth + 1,
                    })

                    # 达到批次大小 → yield
                    if len(file_batch) >= batch_size:
                        yield ("batch", *_flush(), scanned_files, scanned_dirs)

            except PermissionError as e:
                total_errors += 1
                errors.append({"path": entry_path if 'entry_path' in dir() else current_path,
                               "error_type": "permission", "error_message": str(e)})
            except OSError as e:
                total_errors += 1
                errors.append({"path": entry_path if 'entry_path' in dir() else current_path,
                               "error_type": "os_error", "error_message": str(e)})

    # 刷出残余
    if file_batch or errors:
        yield ("batch", *_flush(), scanned_files, scanned_dirs)

    # ---- 自底向上累加目录大小 ----
    sorted_dirs = sorted(dir_sizes.keys(), key=lambda p: p.count(os.sep), reverse=True)
    for dir_path in sorted_dirs:
        parent = os.path.dirname(dir_path)
        if parent in dir_sizes and parent != dir_path:
            dir_sizes[parent]["size"] += dir_sizes[dir_path]["size"]
            dir_sizes[parent]["file_count"] += dir_sizes[dir_path]["file_count"]
            dir_sizes[parent]["dir_count"] += dir_sizes[dir_path]["dir_count"]

    yield ("done", dir_sizes, scanned_files, scanned_dirs, total_errors)


async def run_scan(scan_id: int, root_path: str, max_depth: int = None,
                   exclude_paths: list[str] = None, exclude_extensions: list[str] = None,
                   min_file_size: int = 0):
    """
    异步执行扫描任务。

    扫描在线程池中以生成器方式运行，每积累一批文件就写入数据库并更新进度。
    """
    start_time = time.time()

    exclude_set = set(config.DEFAULT_EXCLUDE_PATHS)
    if exclude_paths:
        exclude_set.update(exclude_paths)
    exclude_ext_set = set(exclude_extensions) if exclude_extensions else set()
    if max_depth is None:
        max_depth = config.MAX_SCAN_DEPTH

    batch_size = config.BATCH_SIZE
    database = await db.get_db()

    # 把同步生成器包成异步迭代器
    loop = asyncio.get_event_loop()
    queue: asyncio.Queue = asyncio.Queue()
    _sentinel = object()

    def _producer():
        gen = _scan_directory_sync(
            root_path, max_depth, exclude_set, exclude_ext_set,
            min_file_size, batch_size,
        )
        for item in gen:
            loop.call_soon_threadsafe(queue.put_nowait, item)
        loop.call_soon_threadsafe(queue.put_nowait, _sentinel)

    _executor.submit(_producer)

    dir_sizes = None
    cumulative_errors = 0

    try:
        while True:
            item = await queue.get()
            if item is _sentinel:
                break

            kind = item[0]

            if kind == "batch":
                _, file_batch, errors, scanned_files, scanned_dirs = item

                # 写入文件批次
                if file_batch:
                    await db.batch_insert_files(database, scan_id, file_batch)

                # 写入错误批次
                if errors:
                    await db.batch_insert_scan_errors(database, scan_id, errors)
                    cumulative_errors += len(errors)

                # 更新进度（轻量 UPDATE，不改 status）
                await db.update_scan_progress(
                    database, scan_id,
                    file_count=scanned_files,
                    dir_count=scanned_dirs,
                    error_count=cumulative_errors,
                )

            elif kind == "done":
                _, ds, scanned_files, scanned_dirs, total_errors = item
                dir_sizes = ds
                cumulative_errors = total_errors

        # ---- 扫描完成：写入目录汇总 ----
        if dir_sizes:
            dir_records = []
            for dir_path, info in dir_sizes.items():
                dir_name = os.path.basename(dir_path) or dir_path
                dir_parent = os.path.dirname(dir_path)
                depth = dir_path.replace(root_path, "").count(os.sep)
                dir_records.append({
                    "path": dir_path,
                    "name": dir_name,
                    "parent_path": dir_parent if dir_parent != dir_path else "",
                    "total_size": info["size"],
                    "file_count": info["file_count"],
                    "dir_count": info["dir_count"],
                    "depth": depth,
                })
            for i in range(0, len(dir_records), batch_size):
                await db.batch_insert_directories(database, scan_id, dir_records[i:i + batch_size])

        # 根目录总大小
        root_size = dir_sizes.get(root_path, {}).get("size", 0) if dir_sizes else 0
        root_files = dir_sizes.get(root_path, {}).get("file_count", 0) if dir_sizes else 0
        root_dirs = dir_sizes.get(root_path, {}).get("dir_count", 0) if dir_sizes else 0

        scan_duration = time.time() - start_time
        await db.update_scan_status(
            database, scan_id, "completed",
            total_size=root_size,
            file_count=root_files,
            dir_count=root_dirs,
            error_count=cumulative_errors,
            scan_duration=round(scan_duration, 2),
        )

    except Exception:
        await db.update_scan_status(database, scan_id, "failed")
        raise
