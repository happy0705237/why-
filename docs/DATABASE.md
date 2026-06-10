# DiskManager 数据库设计文档

> 版本：1.0 | 更新日期：2026-06-09

---

## 1. 概述

- **数据库**：SQLite 3.40+
- **文件位置**：`~/.diskmanager/data.db`（用户目录下，首次运行自动创建）
- **异步驱动**：aiosqlite
- **编码**：UTF-8

### 设计原则

1. **扫描快照隔离**：每次扫描生成独立快照，互不影响
2. **批量写入优化**：使用事务 + executemany 批量插入
3. **查询性能**：对高频查询字段建立索引
4. **数据生命周期**：历史扫描记录可配置保留策略

---

## 2. ER 关系图

```
┌──────────────┐       ┌──────────────────┐
│    scans     │       │  disk_partitions │
│──────────────│       │──────────────────│
│ id (PK)      │       │ id (PK)          │
│ partition_id │──┐    │ letter           │
│ root_path    │  │    │ total_space      │
│ status       │  │    │ used_space       │
│ total_size   │  │    │ free_space       │
│ file_count   │  │    │ fs_type          │
│ dir_count    │  │    │ label            │
│ error_count  │  │    │ updated_at       │
│ started_at   │  │    └──────────────────┘
│ completed_at │  │
│ created_at   │  │    ┌──────────────────┐
└──────────────┘  │    │   directories    │
                  │    │──────────────────│
                  ├───→│ scan_id (FK)     │
                  │    │ path (PK复合)    │
┌──────────────┐  │    │ parent_path      │
│    files     │  │    │ name             │
│──────────────│  │    │ total_size       │
│ scan_id (FK) │──┘    │ file_count       │
│ path (PK复合)│       │ depth            │
│ name         │       │ created_at       │
│ size         │       └──────────────────┘
│ file_type    │
│ modified_at  │       ┌──────────────────┐
│ accessed_at  │       │   scan_errors    │
│ is_dir       │       │──────────────────│
│ parent_path  │       │ scan_id (FK)     │
│ depth        │       │ path             │
│ file_hash    │       │ error_type       │
│ created_at   │       │ error_message    │
└──────────────┘       │ created_at       │
                       └──────────────────┘

┌───────────────────────┐    ┌──────────────────────┐
│ cleanup_suggestions   │    │   scan_config        │
│───────────────────────│    │──────────────────────│
│ id (PK)               │    │ id (PK)              │
│ scan_id (FK)          │    │ key                  │
│ suggestion_type       │    │ value                │
│ target_path           │    │ updated_at           │
│ target_size           │    └──────────────────────┘
│ reason                │
│ confidence            │    ┌──────────────────────┐
│ status                │    │  duplicate_groups    │
│ confirmed_at          │    │──────────────────────│
│ executed_at           │    │ id (PK)              │
│ created_at            │    │ scan_id (FK)         │
└───────────────────────┘    │ file_hash            │
                             │ file_size            │
                             │ file_count           │
                             │ total_wasted         │
                             │ created_at           │
                             └──────────────────────┘

                             ┌──────────────────────┐
                             │  duplicate_files     │
                             │──────────────────────│
                             │ group_id (FK)        │
                             │ file_path            │
                             │ modified_at          │
                             └──────────────────────┘
```

---

## 3. 表结构详细定义

### 3.1 scans — 扫描任务表

每次目录扫描创建一条记录，记录扫描状态和汇总信息。

```sql
CREATE TABLE IF NOT EXISTS scans (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    partition_id    INTEGER,                    -- 关联磁盘分区
    root_path       TEXT    NOT NULL,           -- 扫描根目录路径
    status          TEXT    NOT NULL DEFAULT 'pending',
                                                -- pending / scanning / completed / failed / cancelled
    total_size      INTEGER NOT NULL DEFAULT 0, -- 总大小（字节）
    file_count      INTEGER NOT NULL DEFAULT 0, -- 文件总数
    dir_count       INTEGER NOT NULL DEFAULT 0, -- 目录总数
    error_count     INTEGER NOT NULL DEFAULT 0, -- 错误数
    freed_size      INTEGER NOT NULL DEFAULT 0, -- 清理释放的空间（字节）
    scan_duration   REAL,                       -- 扫描耗时（秒）
    max_depth       INTEGER,                    -- 最大扫描深度（NULL=无限制）
    started_at      TEXT,                       -- 扫描开始时间 (ISO 8601)
    completed_at    TEXT,                       -- 扫描完成时间
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (partition_id) REFERENCES disk_partitions(id)
);

CREATE INDEX idx_scans_status ON scans(status);
CREATE INDEX idx_scans_created ON scans(created_at DESC);
CREATE INDEX idx_scans_root_path ON scans(root_path);
```

### 3.2 disk_partitions — 磁盘分区表

记录系统磁盘分区信息，定期刷新。

```sql
CREATE TABLE IF NOT EXISTS disk_partitions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    letter          TEXT    NOT NULL UNIQUE,     -- 盘符，如 "C:", "D:"
    total_space     INTEGER NOT NULL,            -- 总空间（字节）
    used_space      INTEGER NOT NULL,            -- 已用空间
    free_space      INTEGER NOT NULL,            -- 可用空间
    fs_type         TEXT,                        -- 文件系统类型（NTFS, FAT32...）
    label           TEXT,                        -- 卷标
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);
```

### 3.3 files — 文件快照表

记录某次扫描中每个文件的元信息。这是数据量最大的表。

```sql
CREATE TABLE IF NOT EXISTS files (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id         INTEGER NOT NULL,
    path            TEXT    NOT NULL,            -- 完整文件路径
    name            TEXT    NOT NULL,            -- 文件名
    extension       TEXT,                        -- 扩展名（小写，不含点）
    size            INTEGER NOT NULL DEFAULT 0,  -- 文件大小（字节）
    is_dir          INTEGER NOT NULL DEFAULT 0,  -- 1=目录, 0=文件
    modified_at     TEXT,                        -- 最后修改时间
    accessed_at     TEXT,                        -- 最后访问时间
    parent_path     TEXT,                        -- 父目录路径
    depth           INTEGER NOT NULL DEFAULT 0,  -- 相对于扫描根目录的深度
    file_hash       TEXT,                        -- 文件哈希（延迟计算，初始为 NULL）
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (scan_id) REFERENCES scans(id) ON DELETE CASCADE
);

-- 核心查询索引
CREATE INDEX idx_files_scan_id ON files(scan_id);
CREATE INDEX idx_files_parent ON files(scan_id, parent_path);
CREATE INDEX idx_files_size ON files(scan_id, size DESC);
CREATE INDEX idx_files_extension ON files(scan_id, extension);
CREATE INDEX idx_files_modified ON files(scan_id, modified_at);
CREATE INDEX idx_files_accessed ON files(scan_id, accessed_at);
CREATE INDEX idx_files_hash ON files(scan_id, file_hash) WHERE file_hash IS NOT NULL;

-- 复合索引：按目录统计大小
CREATE INDEX idx_files_dir_size ON files(scan_id, is_dir, parent_path, size);
```

### 3.4 directories — 目录汇总表

预聚合的目录统计数据，避免前端每次都做聚合计算。

```sql
CREATE TABLE IF NOT EXISTS directories (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id         INTEGER NOT NULL,
    path            TEXT    NOT NULL,            -- 目录完整路径
    name            TEXT    NOT NULL,            -- 目录名
    parent_path     TEXT,                        -- 父目录路径
    total_size      INTEGER NOT NULL DEFAULT 0,  -- 目录总大小（含子目录）
    file_count      INTEGER NOT NULL DEFAULT 0,  -- 文件数（含子目录）
    dir_count       INTEGER NOT NULL DEFAULT 0,  -- 子目录数
    depth           INTEGER NOT NULL DEFAULT 0,  -- 深度
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (scan_id) REFERENCES scans(id) ON DELETE CASCADE,
    UNIQUE(scan_id, path)
);

CREATE INDEX idx_dirs_scan ON directories(scan_id);
CREATE INDEX idx_dirs_parent ON directories(scan_id, parent_path);
CREATE INDEX idx_dirs_size ON directories(scan_id, total_size DESC);
CREATE INDEX idx_dirs_depth ON directories(scan_id, depth);
```

### 3.5 cleanup_suggestions — 清理建议表

分析引擎生成的清理建议，用户确认后执行。

```sql
CREATE TABLE IF NOT EXISTS cleanup_suggestions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id         INTEGER NOT NULL,
    suggestion_type TEXT    NOT NULL,            -- temp / cache / log / duplicate / stale / installer
    target_path     TEXT    NOT NULL,            -- 目标文件/目录路径
    target_size     INTEGER NOT NULL DEFAULT 0,  -- 预计可释放空间（字节）
    file_count      INTEGER NOT NULL DEFAULT 1,  -- 涉及文件数
    reason          TEXT    NOT NULL,            -- 推荐理由（人类可读）
    confidence      TEXT    NOT NULL DEFAULT 'medium', -- high / medium / low
    status          TEXT    NOT NULL DEFAULT 'pending', -- pending / confirmed / executed / skipped
    confirmed_at    TEXT,                        -- 用户确认时间
    executed_at     TEXT,                        -- 执行时间
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (scan_id) REFERENCES scans(id) ON DELETE CASCADE
);

CREATE INDEX idx_suggestions_scan ON cleanup_suggestions(scan_id);
CREATE INDEX idx_suggestions_type ON cleanup_suggestions(scan_id, suggestion_type);
CREATE INDEX idx_suggestions_status ON cleanup_suggestions(status);
```

### 3.6 duplicate_groups — 重复文件组表

用于重复文件检测，按哈希值分组。

```sql
CREATE TABLE IF NOT EXISTS duplicate_groups (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id         INTEGER NOT NULL,
    file_hash       TEXT    NOT NULL,            -- 文件 MD5/SHA256 哈希
    file_size       INTEGER NOT NULL,            -- 单个文件大小
    file_count      INTEGER NOT NULL,            -- 重复文件数量
    total_wasted    INTEGER NOT NULL,            -- 浪费的总空间 = file_size × (file_count - 1)
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (scan_id) REFERENCES scans(id) ON DELETE CASCADE
);

CREATE INDEX idx_dup_scan ON duplicate_groups(scan_id);
CREATE INDEX idx_dup_wasted ON duplicate_groups(scan_id, total_wasted DESC);
```

### 3.7 duplicate_files — 重复文件明细表

```sql
CREATE TABLE IF NOT EXISTS duplicate_files (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id        INTEGER NOT NULL,
    file_path       TEXT    NOT NULL,
    modified_at     TEXT,

    FOREIGN KEY (group_id) REFERENCES duplicate_groups(id) ON DELETE CASCADE
);

CREATE INDEX idx_dup_files_group ON duplicate_files(group_id);
```

### 3.8 scan_errors — 扫描错误表

记录扫描过程中遇到的错误，不影响主流程。

```sql
CREATE TABLE IF NOT EXISTS scan_errors (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id         INTEGER NOT NULL,
    path            TEXT    NOT NULL,            -- 出错的路径
    error_type      TEXT    NOT NULL,            -- permission / path_too_long / file_locked / unknown
    error_message   TEXT,                        -- 原始错误信息
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (scan_id) REFERENCES scans(id) ON DELETE CASCADE
);

CREATE INDEX idx_errors_scan ON scan_errors(scan_id);
```

### 3.9 scan_config — 配置表

存储应用配置项，键值对形式。

```sql
CREATE TABLE IF NOT EXISTS scan_config (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    key             TEXT    NOT NULL UNIQUE,
    value           TEXT,
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- 初始化默认配置
INSERT INTO scan_config (key, value) VALUES
    ('max_scan_depth', '20'),
    ('scan_timeout', '300'),
    ('auto_cleanup_to_recycle_bin', 'true'),
    ('history_retention_days', '90'),
    ('min_file_size_for_hash', '1048576'),       -- 1MB 以下不计算哈希
    ('stale_file_days', '180');                   -- 超过180天未访问视为长期未访问
```

---

## 4. 数据生命周期

### 4.1 数据量估算

| 表 | 单次扫描（10万文件） | 存储空间 |
|----|---------------------|---------|
| scans | 1 行 | ~1 KB |
| files | 10 万行 | ~50 MB |
| directories | ~1 万行 | ~5 MB |
| cleanup_suggestions | ~100 行 | ~10 KB |
| scan_errors | ~100 行 | ~10 KB |
| **合计** | - | **~55 MB / 次扫描** |

### 4.2 数据清理策略

```
自动清理规则：
1. 保留最近 N 次扫描记录（默认 N=10）
2. 保留最近 N 天的扫描记录（默认 N=90 天）
3. 清理时级联删除关联的 files、directories、suggestions 等
4. 用户可手动触发清理

清理时机：
- 每次新扫描完成后检查是否需要清理
- 应用启动时检查过期数据
```

### 4.3 数据库维护

```
定期维护：
- VACUUM：每月或数据清理后执行，回收空间
- ANALYZE：更新查询优化器统计信息
- PRAGMA integrity_check：启动时检查完整性
```

---

## 5. 常用查询模式

### 5.1 获取目录树（指定深度）

```sql
-- 获取 scan_id=1 下 depth=1 的所有目录，按大小降序
SELECT path, name, total_size, file_count, dir_count
FROM directories
WHERE scan_id = 1 AND depth = 1
ORDER BY total_size DESC;
```

### 5.2 获取子目录内容

```sql
-- 获取某个目录下的直接子项（文件+目录）
SELECT path, name, size, is_dir, extension, modified_at
FROM files
WHERE scan_id = 1 AND parent_path = 'C:\Users\ASUS\Documents'
ORDER BY size DESC;
```

### 5.3 Top N 大文件

```sql
-- Top 50 最大文件
SELECT path, name, size, extension, modified_at
FROM files
WHERE scan_id = 1 AND is_dir = 0
ORDER BY size DESC
LIMIT 50;
```

### 5.4 按文件类型统计

```sql
-- 按扩展名统计空间占用
SELECT
    COALESCE(extension, '(无扩展名)') AS ext,
    COUNT(*) AS file_count,
    SUM(size) AS total_size
FROM files
WHERE scan_id = 1 AND is_dir = 0
GROUP BY extension
ORDER BY total_size DESC;
```

### 5.5 长期未访问文件

```sql
-- 超过 180 天未访问的大文件（>1MB）
SELECT path, name, size, accessed_at
FROM files
WHERE scan_id = 1
  AND is_dir = 0
  AND size > 1048576
  AND accessed_at < datetime('now', '-180 days')
ORDER BY size DESC
LIMIT 100;
```

---

## 6. 迁移策略

使用版本号管理数据库 schema 变更：

```sql
-- 在 scan_config 表中存储版本号
INSERT INTO scan_config (key, value) VALUES ('db_version', '1');
```

启动时检查 `db_version`，按需执行增量迁移脚本。迁移脚本存放在 `backend/migrations/` 目录。
