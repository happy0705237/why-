# DiskManager API 接口设计文档

> 版本：1.0 | 更新日期：2026-06-09

---

## 1. 概述

- **基础地址**：`http://127.0.0.1:8765`
- **协议**：HTTP/1.1 + WebSocket
- **数据格式**：JSON
- **字符编码**：UTF-8
- **时间格式**：ISO 8601（`2026-06-09T14:30:00`）

### 1.1 通用响应格式

**成功响应：**
```json
{
    "code": 200,
    "message": "success",
    "data": { ... }
}
```

**错误响应：**
```json
{
    "code": 400,
    "message": "错误描述",
    "detail": "详细错误信息（仅开发模式）"
}
```

### 1.2 HTTP 状态码约定

| 状态码 | 含义 |
|--------|------|
| 200 | 成功 |
| 201 | 创建成功 |
| 204 | 成功但无返回内容 |
| 400 | 请求参数错误 |
| 404 | 资源不存在 |
| 409 | 冲突（如扫描任务正在运行） |
| 500 | 服务器内部错误 |

---

## 2. API 端点列表

### 2.1 磁盘分区

#### `GET /api/disks` — 获取磁盘分区信息

获取系统所有磁盘分区的使用情况。

**请求参数：** 无

**响应示例：**
```json
{
    "code": 200,
    "data": {
        "partitions": [
            {
                "letter": "C:",
                "label": "Windows",
                "total_space": 512000000000,
                "used_space": 320000000000,
                "free_space": 192000000000,
                "usage_percent": 62.5,
                "fs_type": "NTFS",
                "mount_point": "C:\\"
            },
            {
                "letter": "D:",
                "label": "Data",
                "total_space": 1024000000000,
                "used_space": 450000000000,
                "free_space": 574000000000,
                "usage_percent": 43.9,
                "fs_type": "NTFS",
                "mount_point": "D:\\"
            }
        ]
    }
}
```

---

### 2.2 扫描任务

#### `POST /api/scan` — 创建扫描任务

启动一个目录扫描任务。

**请求体：**
```json
{
    "path": "C:\\Users\\ASUS",
    "max_depth": null,
    "exclude_paths": [
        "C:\\Users\\ASUS\\.git",
        "C:\\Users\\ASUS\\node_modules"
    ],
    "exclude_extensions": [],
    "min_file_size": 0
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| path | string | 是 | 要扫描的目录路径 |
| max_depth | integer | 否 | 最大扫描深度，null=无限制 |
| exclude_paths | string[] | 否 | 排除的目录路径列表 |
| exclude_extensions | string[] | 否 | 排除的文件扩展名列表 |
| min_file_size | integer | 否 | 最小文件大小（字节），小于此值不记录 |

**响应示例（201 Created）：**
```json
{
    "code": 201,
    "data": {
        "scan_id": 1,
        "status": "scanning",
        "message": "扫描任务已启动"
    }
}
```

**错误响应（409 Conflict）：**
```json
{
    "code": 409,
    "message": "已有扫描任务正在运行",
    "data": {
        "running_scan_id": 1,
        "running_scan_path": "D:\\Projects"
    }
}
```

---

#### `GET /api/scan/{scan_id}` — 获取扫描任务状态

查询指定扫描任务的状态和摘要信息。

**路径参数：**
| 参数 | 类型 | 说明 |
|------|------|------|
| scan_id | integer | 扫描任务 ID |

**响应示例：**
```json
{
    "code": 200,
    "data": {
        "id": 1,
        "root_path": "C:\\Users\\ASUS",
        "status": "completed",
        "total_size": 52428800000,
        "file_count": 85432,
        "dir_count": 4521,
        "error_count": 3,
        "freed_size": 0,
        "scan_duration": 8.5,
        "started_at": "2026-06-09T14:30:00",
        "completed_at": "2026-06-09T14:30:08",
        "progress": {
            "scanned_files": 85432,
            "scanned_dirs": 4521,
            "current_path": "C:\\Users\\ASUS\\Documents"
        }
    }
}
```

**status 枚举值：**
| 值 | 说明 |
|----|------|
| pending | 等待中 |
| scanning | 扫描中 |
| completed | 已完成 |
| failed | 失败 |
| cancelled | 已取消 |

---

#### `DELETE /api/scan/{scan_id}` — 删除扫描记录

删除指定扫描任务及其所有关联数据（files、directories、scan_errors 通过 ON DELETE CASCADE 级联删除）。

**约束：**
- 不能删除状态为 `scanning` 的任务（返回 409）

**路径参数：**
| 参数 | 类型 | 说明 |
|------|------|------|
| scan_id | integer | 扫描任务 ID |

**响应（200）：**
```json
{
    "code": 200,
    "message": "扫描记录已删除",
    "data": {"root_path": "C:\\Users\\ASUS"}
}
```

**错误响应（404）：**
```json
{"detail": "扫描任务不存在"}
```

**错误响应（409）：**
```json
{"detail": "不能删除正在扫描的任务"}
```

---

#### `GET /api/scans` — 获取扫描历史列表

获取所有扫描任务的历史记录。

**查询参数：**
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| page | integer | 1 | 页码 |
| page_size | integer | 20 | 每页数量 |
| status | string | null | 按状态筛选 |

**响应示例：**
```json
{
    "code": 200,
    "data": {
        "total": 15,
        "page": 1,
        "page_size": 20,
        "items": [
            {
                "id": 1,
                "root_path": "C:\\Users\\ASUS",
                "status": "completed",
                "total_size": 52428800000,
                "file_count": 85432,
                "scan_duration": 8.5,
                "completed_at": "2026-06-09T14:30:08"
            }
        ]
    }
}
```

---

### 2.3 目录树查询

#### `GET /api/scan/{scan_id}/tree` — 获取目录树

获取扫描结果的目录树结构，支持逐层查询。

**路径参数：**
| 参数 | 类型 | 说明 |
|------|------|------|
| scan_id | integer | 扫描任务 ID |

**查询参数：**
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| path | string | 扫描根目录 | 要查询的目录路径 |
| depth | integer | 1 | 返回层级深度（1=直接子项） |
| sort_by | string | "size" | 排序字段：size / name / count |
| order | string | "desc" | 排序方向：asc / desc |
| include_files | boolean | true | 是否包含文件（否则只返回目录） |

**响应示例：**
```json
{
    "code": 200,
    "data": {
        "scan_id": 1,
        "parent_path": "C:\\Users",
        "current_path": "C:\\Users\\ASUS",
        "current_size": 52428800000,
        "breadcrumb": [
            {"name": "C:", "path": "C:\\"},
            {"name": "Users", "path": "C:\\Users"},
            {"name": "ASUS", "path": "C:\\Users\\ASUS"}
        ],
        "items": [
            {
                "path": "C:\\Users\\ASUS\\Documents",
                "name": "Documents",
                "is_dir": true,
                "size": 15728640000,
                "file_count": 12543,
                "dir_count": 234,
                "size_percent": 30.0
            },
            {
                "path": "C:\\Users\\ASUS\\Downloads",
                "name": "Downloads",
                "is_dir": true,
                "size": 10485760000,
                "file_count": 856,
                "dir_count": 45,
                "size_percent": 20.0
            },
            {
                "path": "C:\\Users\\ASUS\\Desktop",
                "name": "Desktop",
                "is_dir": true,
                "size": 5242880000,
                "file_count": 342,
                "dir_count": 12,
                "size_percent": 10.0
            },
            {
                "path": "C:\\Users\\ASUS\\big_video.mp4",
                "name": "big_video.mp4",
                "is_dir": false,
                "size": 2147483648,
                "extension": "mp4",
                "modified_at": "2026-05-15T10:30:00",
                "size_percent": 4.1
            }
        ],
        "summary": {
            "total_items": 56,
            "total_dirs": 42,
            "total_files": 14,
            "others_size": 3221225472,
            "others_count": 84270
        }
    }
}
```

**说明：**
- `items` 按大小降序排列，最多返回 Top 50
- 超出 Top 50 的合并为 `others` 项
- `breadcrumb` 用于前端面包屑导航
- `size_percent` 相对于当前目录的父目录计算

---

### 2.4 文件查询

#### `GET /api/scan/{scan_id}/files/top` — 大文件排行

获取指定扫描中最大的 N 个文件。

**查询参数：**
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| limit | integer | 50 | 返回数量 |
| offset | integer | 0 | 偏移量（分页） |
| extension | string | null | 按扩展名筛选 |
| min_size | integer | null | 最小文件大小（字节） |
| sort_by | string | "size" | 排序字段：size / name / modified_at |
| order | string | "desc" | 排序方向 |

**响应示例：**
```json
{
    "code": 200,
    "data": {
        "total": 85000,
        "items": [
            {
                "path": "C:\\Users\\ASUS\\Videos\\recording.mp4",
                "name": "recording.mp4",
                "size": 4294967296,
                "extension": "mp4",
                "modified_at": "2026-03-20T16:45:00",
                "parent_dir": "C:\\Users\\ASUS\\Videos"
            }
        ]
    }
}
```

---

#### `GET /api/scan/{scan_id}/files/types` — 按文件类型统计

按扩展名分组统计空间占用。

**响应示例：**
```json
{
    "code": 200,
    "data": {
        "categories": [
            {
                "extension": "mp4",
                "label": "视频文件",
                "file_count": 45,
                "total_size": 25769803776,
                "size_percent": 49.1
            },
            {
                "extension": "jpg",
                "label": "图片文件",
                "file_count": 12500,
                "total_size": 8589934592,
                "size_percent": 16.4
            },
            {
                "extension": "pdf",
                "label": "PDF 文档",
                "file_count": 320,
                "total_size": 1073741824,
                "size_percent": 2.0
            },
            {
                "extension": "(无扩展名)",
                "label": "其他",
                "file_count": 500,
                "total_size": 536870912,
                "size_percent": 1.0
            }
        ],
        "top_extensions": ["mp4", "jpg", "pdf", "zip", "docx"],
        "total_size": 52428800000
    }
}
```

---

### 2.5 清理建议

#### `GET /api/scan/{scan_id}/suggestions` — 获取清理建议

基于扫描结果生成清理建议。

**查询参数：**
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| type | string | null | 按建议类型筛选 |
| confidence | string | null | 按置信度筛选：high / medium / low |
| min_size | integer | null | 最小文件大小 |

**建议类型枚举：**
| type | 说明 | 示例 |
|------|------|------|
| temp | 临时文件 | %TEMP% 目录、Windows\Temp |
| cache | 缓存文件 | 浏览器缓存、应用缓存 |
| log | 日志文件 | *.log、日志目录 |
| stale | 长期未访问 | 超过 180 天未访问的大文件 |
| installer | 安装包残留 | Downloads 中的 .msi/.exe |
| duplicate | 重复文件 | 哈希完全相同的文件 |

**响应示例：**
```json
{
    "code": 200,
    "data": {
        "total_suggestions": 12,
        "total_reclaimable": 3221225472,
        "by_type": {
            "temp": {"count": 3, "size": 1073741824},
            "cache": {"count": 2, "size": 536870912},
            "log": {"count": 4, "size": 268435456},
            "stale": {"count": 2, "size": 1073741824},
            "installer": {"count": 1, "size": 268435456}
        },
        "suggestions": [
            {
                "id": 1,
                "type": "temp",
                "target_path": "C:\\Users\\ASUS\\AppData\\Local\\Temp",
                "target_size": 1073741824,
                "file_count": 1523,
                "reason": "系统临时目录包含 1,523 个临时文件，总计 1.0 GB。这些文件已被应用程序遗留，可以安全清理。",
                "confidence": "high",
                "status": "pending",
                "oldest_file": "2025-01-15T08:00:00",
                "newest_file": "2026-06-08T22:30:00"
            },
            {
                "id": 2,
                "type": "stale",
                "target_path": "C:\\Users\\ASUS\\Downloads\\old_backup.zip",
                "target_size": 536870912,
                "file_count": 1,
                "reason": "该文件已 280 天未被访问，文件大小 512 MB。建议确认是否仍需要。",
                "confidence": "medium",
                "status": "pending",
                "last_accessed": "2025-09-02T14:20:00"
            }
        ]
    }
}
```

---

#### `POST /api/scan/{scan_id}/suggestions/confirm` — 确认清理建议

用户确认要执行的清理建议。

**请求体：**
```json
{
    "suggestion_ids": [1, 2, 5],
    "action": "confirm"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| suggestion_ids | integer[] | 要确认的建议 ID 列表 |
| action | string | confirm=确认 / skip=跳过 |

**响应：**
```json
{
    "code": 200,
    "data": {
        "confirmed": 3,
        "total_size": 1879048192
    }
}
```

---

#### `POST /api/cleanup/execute` — 执行清理

执行已确认的清理操作。文件移动到回收站，非物理删除。

**请求体：**
```json
{
    "scan_id": 1,
    "suggestion_ids": [1, 2, 5],
    "delete_to_recycle_bin": true,
    "dry_run": false
}
```

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| scan_id | integer | - | 扫描任务 ID |
| suggestion_ids | integer[] | - | 要执行的建议 ID 列表 |
| delete_to_recycle_bin | boolean | true | 是否删除到回收站 |
| dry_run | boolean | false | 模拟执行（不实际删除） |

**响应：**
```json
{
    "code": 200,
    "data": {
        "executed": 3,
        "success_count": 2,
        "failed_count": 1,
        "total_freed": 1610612736,
        "results": [
            {
                "suggestion_id": 1,
                "status": "success",
                "freed": 1073741824,
                "files_deleted": 1523
            },
            {
                "suggestion_id": 2,
                "status": "success",
                "freed": 536870912,
                "files_deleted": 1
            },
            {
                "suggestion_id": 5,
                "status": "failed",
                "error": "文件正在被其他程序使用",
                "freed": 0,
                "files_deleted": 0
            }
        ]
    }
}
```

---

### 2.6 重复文件

#### `GET /api/scan/{scan_id}/duplicates` — 获取重复文件列表

获取哈希相同的重复文件分组。

**查询参数：**
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| min_count | integer | 2 | 每组最少文件数 |
| min_size | integer | 1048576 | 单个文件最小大小（默认 1MB） |
| sort_by | string | "total_wasted" | 排序字段：total_wasted / file_size / file_count |
| limit | integer | 50 | 返回组数 |

**响应示例：**
```json
{
    "code": 200,
    "data": {
        "total_groups": 15,
        "total_wasted": 2147483648,
        "groups": [
            {
                "group_id": 1,
                "file_hash": "a1b2c3d4e5f6...",
                "file_size": 524288000,
                "file_count": 4,
                "total_wasted": 1572864000,
                "files": [
                    {
                        "path": "C:\\Users\\ASUS\\Downloads\\photo.jpg",
                        "modified_at": "2026-01-15T10:00:00"
                    },
                    {
                        "path": "C:\\Users\\ASUS\\Documents\\photo (1).jpg",
                        "modified_at": "2026-02-20T14:30:00"
                    },
                    {
                        "path": "C:\\Users\\ASUS\\Desktop\\photo.jpg",
                        "modified_at": "2026-03-10T09:15:00"
                    },
                    {
                        "path": "D:\\Backup\\photo.jpg",
                        "modified_at": "2026-01-15T10:00:00"
                    }
                ]
            }
        ]
    }
}
```

---

### 2.7 应用配置

#### `GET /api/config` — 获取配置

**响应示例：**
```json
{
    "code": 200,
    "data": {
        "max_scan_depth": 20,
        "scan_timeout": 300,
        "auto_cleanup_to_recycle_bin": true,
        "history_retention_days": 90,
        "min_file_size_for_hash": 1048576,
        "stale_file_days": 180,
        "exclude_paths": [
            "C:\\$Recycle.Bin",
            "C:\\System Volume Information",
            "C:\\Windows"
        ]
    }
}
```

#### `PUT /api/config` — 更新配置

**请求体：**
```json
{
    "stale_file_days": 90,
    "exclude_paths": ["C:\\$Recycle.Bin", "D:\\Games"]
}
```

---

### 2.8 常用路径

#### `GET /api/common-paths` — 获取常用目录路径

返回系统常用目录及其存在状态，用于前端快捷扫描入口。

**请求参数：** 无

**响应示例：**
```json
{
    "code": 200,
    "data": {
        "paths": [
            {"name": "项目目录", "path": "E:\\Claude工作文件\\disk-manager", "exists": true},
            {"name": "用户目录", "path": "C:\\Users\\ASUS", "exists": true},
            {"name": "桌面", "path": "C:\\Users\\ASUS\\Desktop", "exists": true},
            {"name": "下载", "path": "C:\\Users\\ASUS\\Downloads", "exists": true},
            {"name": "磁盘 C:", "path": "C:\\", "exists": true},
            {"name": "磁盘 D:", "path": "D:\\", "exists": true}
        ]
    }
}
```

---

## 3. WebSocket 协议

### 3.1 连接地址

```
ws://127.0.0.1:8765/ws/monitor
```

### 3.2 消息格式

所有消息使用 JSON 格式，包含 `type` 字段标识消息类型。

**服务端 → 客户端消息类型：**

#### scan_progress — 扫描进度

```json
{
    "type": "scan_progress",
    "data": {
        "scan_id": 1,
        "status": "scanning",
        "scanned_files": 45000,
        "scanned_dirs": 2100,
        "current_path": "C:\\Users\\ASUS\\Documents\\Projects",
        "elapsed_time": 5.2,
        "speed": 8653,                  // 每秒扫描文件数
        "total_size_so_far": 25000000000
    }
}
```

#### scan_completed — 扫描完成

```json
{
    "type": "scan_completed",
    "data": {
        "scan_id": 1,
        "status": "completed",
        "total_size": 52428800000,
        "file_count": 85432,
        "dir_count": 4521,
        "scan_duration": 8.5
    }
}
```

#### scan_error — 扫描错误

```json
{
    "type": "scan_error",
    "data": {
        "scan_id": 1,
        "path": "C:\\System Volume Information",
        "error_type": "permission",
        "message": "Access denied"
    }
}
```

#### file_event — 文件变化事件（V1.2）

```json
{
    "type": "file_event",
    "data": {
        "event_type": "created",        // created / modified / deleted
        "path": "C:\\Users\\ASUS\\Documents\\new_file.txt",
        "is_dir": false,
        "size": 1024,
        "timestamp": "2026-06-09T14:35:00"
    }
}
```

**客户端 → 服务端消息类型：**

#### subscribe — 订阅事件

```json
{
    "type": "subscribe",
    "channels": ["scan_progress", "file_event"]
}
```

#### ping — 心跳

```json
{
    "type": "ping"
}
```

**服务端响应：**
```json
{
    "type": "pong",
    "timestamp": "2026-06-09T14:35:00"
}
```

---

## 4. API 与功能映射

| PRD 功能 | API 端点 | 页面 |
|---------|---------|------|
| F01 磁盘分区总览 | GET /api/disks | Dashboard |
| F02 目录扫描 | POST /api/scan | Dashboard |
| F03 TreeMap 可视化 | GET /api/scan/{id}/tree | 扫描详情 |
| F04 逐层下钻 | GET /api/scan/{id}/tree?path=... | 扫描详情 |
| F05 大文件排行 | GET /api/scan/{id}/files/top | 大文件页 |
| F06 按类型统计 | GET /api/scan/{id}/files/types | 扫描详情 |
| F07 Web 仪表盘 | 全部 API | 全部页面 |
| F09-F12 清理建议 | GET /api/scan/{id}/suggestions | 清理建议页 |
| F13 清理建议卡片 | GET /api/scan/{id}/suggestions | 清理建议页 |
| F14 确认执行清理 | POST /api/cleanup/execute | 清理建议页 |
| F15 扫描历史 | GET /api/scans | 历史记录页 |
| F16 实时监控 | WS /ws/monitor | 监控面板 |
| F18 自定义规则 | PUT /api/config | 设置页 |
