"""SQLite 数据库操作层"""
import aiosqlite
from pathlib import Path
from backend.config import DB_PATH, ensure_data_dir

# 数据库连接单例
_db: aiosqlite.Connection | None = None


async def get_db() -> aiosqlite.Connection:
    """获取数据库连接"""
    global _db
    if _db is None:
        from backend.config import DB_PATH
        if DB_PATH != ":memory:":
            ensure_data_dir()
        _db = await aiosqlite.connect(DB_PATH)
        _db.row_factory = aiosqlite.Row
        if DB_PATH != ":memory:":
            await _db.execute("PRAGMA journal_mode=WAL")
        await _db.execute("PRAGMA foreign_keys=ON")
        await init_tables(_db)
    return _db


async def close_db():
    """关闭数据库连接"""
    global _db
    if _db:
        await _db.close()
        _db = None


async def init_tables(db: aiosqlite.Connection):
    """初始化数据库表"""
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS scans (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            root_path       TEXT    NOT NULL,
            status          TEXT    NOT NULL DEFAULT 'pending',
            total_size      INTEGER NOT NULL DEFAULT 0,
            file_count      INTEGER NOT NULL DEFAULT 0,
            dir_count       INTEGER NOT NULL DEFAULT 0,
            error_count     INTEGER NOT NULL DEFAULT 0,
            scan_duration   REAL,
            started_at      TEXT,
            completed_at    TEXT,
            created_at      TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
        );

        CREATE INDEX IF NOT EXISTS idx_scans_status ON scans(status);
        CREATE INDEX IF NOT EXISTS idx_scans_created ON scans(created_at DESC);

        CREATE TABLE IF NOT EXISTS files (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_id         INTEGER NOT NULL,
            path            TEXT    NOT NULL,
            name            TEXT    NOT NULL,
            extension       TEXT,
            size            INTEGER NOT NULL DEFAULT 0,
            is_dir          INTEGER NOT NULL DEFAULT 0,
            modified_at     TEXT,
            parent_path     TEXT,
            depth           INTEGER NOT NULL DEFAULT 0,
            created_at      TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (scan_id) REFERENCES scans(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_files_scan_id ON files(scan_id);
        CREATE INDEX IF NOT EXISTS idx_files_parent ON files(scan_id, parent_path);
        CREATE INDEX IF NOT EXISTS idx_files_size ON files(scan_id, size DESC);
        CREATE INDEX IF NOT EXISTS idx_files_extension ON files(scan_id, extension);

        CREATE TABLE IF NOT EXISTS directories (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_id         INTEGER NOT NULL,
            path            TEXT    NOT NULL,
            name            TEXT    NOT NULL,
            parent_path     TEXT,
            total_size      INTEGER NOT NULL DEFAULT 0,
            file_count      INTEGER NOT NULL DEFAULT 0,
            dir_count       INTEGER NOT NULL DEFAULT 0,
            depth           INTEGER NOT NULL DEFAULT 0,
            created_at      TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (scan_id) REFERENCES scans(id) ON DELETE CASCADE,
            UNIQUE(scan_id, path)
        );

        CREATE INDEX IF NOT EXISTS idx_dirs_scan ON directories(scan_id);
        CREATE INDEX IF NOT EXISTS idx_dirs_parent ON directories(scan_id, parent_path);
        CREATE INDEX IF NOT EXISTS idx_dirs_size ON directories(scan_id, total_size DESC);

        CREATE TABLE IF NOT EXISTS scan_errors (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_id         INTEGER NOT NULL,
            path            TEXT    NOT NULL,
            error_type      TEXT    NOT NULL,
            error_message   TEXT,
            created_at      TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (scan_id) REFERENCES scans(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_errors_scan ON scan_errors(scan_id);
    """)
    await db.commit()


async def create_scan(db: aiosqlite.Connection, root_path: str) -> int:
    """创建扫描任务"""
    cursor = await db.execute(
        "INSERT INTO scans (root_path, status, started_at) VALUES (?, 'scanning', datetime('now', 'localtime'))",
        (root_path,)
    )
    await db.commit()
    return cursor.lastrowid


async def update_scan_status(db: aiosqlite.Connection, scan_id: int, status: str,
                              total_size: int = 0, file_count: int = 0,
                              dir_count: int = 0, error_count: int = 0,
                              scan_duration: float = 0):
    """更新扫描状态"""
    await db.execute(
        """UPDATE scans SET status=?, total_size=?, file_count=?, dir_count=?,
           error_count=?, scan_duration=?, completed_at=datetime('now','localtime')
           WHERE id=?""",
        (status, total_size, file_count, dir_count, error_count, scan_duration, scan_id)
    )
    await db.commit()


async def batch_insert_files(db: aiosqlite.Connection, scan_id: int, files: list[dict]):
    """批量插入文件记录"""
    if not files:
        return
    await db.executemany(
        """INSERT INTO files (scan_id, path, name, extension, size, is_dir, modified_at, parent_path, depth)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [(scan_id, f["path"], f["name"], f["extension"], f["size"],
          f["is_dir"], f["modified_at"], f["parent_path"], f["depth"]) for f in files]
    )
    await db.commit()


async def batch_insert_directories(db: aiosqlite.Connection, scan_id: int, dirs: list[dict]):
    """批量插入/更新目录汇总"""
    if not dirs:
        return
    await db.executemany(
        """INSERT OR REPLACE INTO directories (scan_id, path, name, parent_path, total_size, file_count, dir_count, depth)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        [(scan_id, d["path"], d["name"], d["parent_path"], d["total_size"],
          d["file_count"], d["dir_count"], d["depth"]) for d in dirs]
    )
    await db.commit()


async def insert_scan_error(db: aiosqlite.Connection, scan_id: int, path: str,
                             error_type: str, error_message: str):
    """插入扫描错误"""
    await db.execute(
        "INSERT INTO scan_errors (scan_id, path, error_type, error_message) VALUES (?, ?, ?, ?)",
        (scan_id, path, error_type, error_message)
    )


async def update_scan_progress(db: aiosqlite.Connection, scan_id: int,
                                file_count: int, dir_count: int, error_count: int):
    """更新扫描进度（不改变 status/completed_at）"""
    await db.execute(
        "UPDATE scans SET file_count=?, dir_count=?, error_count=? WHERE id=?",
        (file_count, dir_count, error_count, scan_id)
    )
    await db.commit()


async def batch_insert_scan_errors(db: aiosqlite.Connection, scan_id: int, errors: list[dict]):
    """批量插入扫描错误"""
    if not errors:
        return
    await db.executemany(
        "INSERT INTO scan_errors (scan_id, path, error_type, error_message) VALUES (?, ?, ?, ?)",
        [(scan_id, e["path"], e["error_type"], e["error_message"]) for e in errors]
    )
    await db.commit()


async def get_scan(db: aiosqlite.Connection, scan_id: int) -> dict | None:
    """获取扫描任务信息"""
    cursor = await db.execute("SELECT * FROM scans WHERE id=?", (scan_id,))
    row = await cursor.fetchone()
    return dict(row) if row else None


async def get_scans(db: aiosqlite.Connection, page: int = 1, page_size: int = 20) -> dict:
    """获取扫描历史列表"""
    offset = (page - 1) * page_size
    cursor = await db.execute(
        "SELECT * FROM scans ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (page_size, offset)
    )
    rows = await cursor.fetchall()
    count_cursor = await db.execute("SELECT COUNT(*) FROM scans")
    total = (await count_cursor.fetchone())[0]
    return {"total": total, "page": page, "page_size": page_size, "items": [dict(r) for r in rows]}


async def get_tree_items(db: aiosqlite.Connection, scan_id: int, parent_path: str,
                          sort_by: str = "size", order: str = "desc",
                          include_files: bool = True, limit: int = 50) -> list[dict]:
    """获取目录树子项"""
    order_dir = "DESC" if order == "desc" else "ASC"
    sort_field = {"size": "size", "name": "name", "count": "file_count"}.get(sort_by, "size")

    # 获取子目录
    cursor = await db.execute(
        f"""SELECT path, name, 1 as is_dir, total_size as size, file_count, dir_count, 0 as depth
            FROM directories WHERE scan_id=? AND parent_path=?
            ORDER BY {sort_field} {order_dir}""",
        (scan_id, parent_path)
    )
    dirs = [dict(r) for r in await cursor.fetchall()]

    items = dirs

    if include_files:
        cursor = await db.execute(
            f"""SELECT path, name, 0 as is_dir, size, extension, modified_at
                FROM files WHERE scan_id=? AND parent_path=? AND is_dir=0
                ORDER BY {sort_field} {order_dir}""",
            (scan_id, parent_path)
        )
        files = [dict(r) for r in await cursor.fetchall()]
        items.extend(files)

    # 按大小排序后取 top N
    items.sort(key=lambda x: x.get("size", 0), reverse=(order == "desc"))

    if len(items) > limit:
        others_size = sum(item.get("size", 0) for item in items[limit:])
        others_count = len(items) - limit
        items = items[:limit]
        items.append({
            "path": "__others__",
            "name": f"其他 ({others_count} 项)",
            "is_dir": False,
            "size": others_size,
            "is_others": True,
        })

    return items


async def get_directory_info(db: aiosqlite.Connection, scan_id: int, path: str) -> dict | None:
    """获取目录详细信息"""
    cursor = await db.execute(
        "SELECT * FROM directories WHERE scan_id=? AND path=?",
        (scan_id, path)
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def get_top_files(db: aiosqlite.Connection, scan_id: int, limit: int = 50,
                         offset: int = 0, extension: str = None,
                         sort_by: str = "size", order: str = "desc") -> dict:
    """获取大文件排行"""
    order_dir = "DESC" if order == "desc" else "ASC"
    sort_field = {"size": "size", "name": "name", "modified_at": "modified_at"}.get(sort_by, "size")

    where = "scan_id=? AND is_dir=0"
    params = [scan_id]
    if extension:
        where += " AND extension=?"
        params.append(extension)

    # 总数
    count_cursor = await db.execute(f"SELECT COUNT(*) FROM files WHERE {where}", params)
    total = (await count_cursor.fetchone())[0]

    # 分页查询
    cursor = await db.execute(
        f"""SELECT path, name, size, extension, modified_at, parent_path
            FROM files WHERE {where}
            ORDER BY {sort_field} {order_dir}
            LIMIT ? OFFSET ?""",
        params + [limit, offset]
    )
    items = [dict(r) for r in await cursor.fetchall()]

    return {"total": total, "items": items}


async def get_file_types(db: aiosqlite.Connection, scan_id: int) -> list[dict]:
    """按文件类型统计"""
    cursor = await db.execute(
        """SELECT
               COALESCE(extension, '') AS extension,
               COUNT(*) AS file_count,
               SUM(size) AS total_size
           FROM files
           WHERE scan_id=? AND is_dir=0
           GROUP BY extension
           ORDER BY total_size DESC""",
        (scan_id,)
    )
    rows = [dict(r) for r in await cursor.fetchall()]

    # 计算总大小
    total_size = sum(r["total_size"] for r in rows)
    for r in rows:
        r["size_percent"] = round(r["total_size"] / total_size * 100, 1) if total_size > 0 else 0

    return rows


async def get_scan_progress(db: aiosqlite.Connection, scan_id: int) -> dict:
    """获取扫描进度"""
    cursor = await db.execute(
        "SELECT file_count, dir_count, error_count FROM scans WHERE id=?",
        (scan_id,)
    )
    row = await cursor.fetchone()
    if not row:
        return {"file_count": 0, "dir_count": 0, "error_count": 0}
    return dict(row)


async def get_current_path(db: aiosqlite.Connection, scan_id: int) -> str:
    """获取当前扫描路径（最后插入的文件路径）"""
    cursor = await db.execute(
        "SELECT parent_path FROM files WHERE scan_id=? ORDER BY id DESC LIMIT 1",
        (scan_id,)
    )
    row = await cursor.fetchone()
    return row[0] if row else ""


async def get_scan_errors(db: aiosqlite.Connection, scan_id: int,
                          limit: int = 50, offset: int = 0) -> dict:
    """获取扫描错误列表"""
    count_cursor = await db.execute(
        "SELECT COUNT(*) FROM scan_errors WHERE scan_id=?", (scan_id,)
    )
    total = (await count_cursor.fetchone())[0]

    cursor = await db.execute(
        """SELECT path, error_type, error_message, created_at
           FROM scan_errors WHERE scan_id=?
           ORDER BY id LIMIT ? OFFSET ?""",
        (scan_id, limit, offset)
    )
    items = [dict(r) for r in await cursor.fetchall()]

    # 按错误类型汇总
    type_cursor = await db.execute(
        """SELECT error_type, COUNT(*) AS cnt
           FROM scan_errors WHERE scan_id=?
           GROUP BY error_type ORDER BY cnt DESC""",
        (scan_id,)
    )
    by_type = {row["error_type"]: row["cnt"] for row in await type_cursor.fetchall()}

    return {"total": total, "by_type": by_type, "items": items}
