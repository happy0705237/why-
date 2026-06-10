# 🖴 DiskManager

Windows 本地磁盘空间管理工具。用 TreeMap 让目录大小"一目了然"，逐层下钻定位空间占用来源。

> V1.0 MVP — 只读扫描 + 可视化分析，不做任何删除操作。

## 功能

| 功能 | 说明 |
|------|------|
| 📊 磁盘总览 | 各分区容量、已用、可用、使用率一目了然 |
| 📂 目录扫描 | 递归扫描指定目录，统计文件大小、数量、目录数 |
| 🗺️ TreeMap 可视化 | ECharts TreeMap 按文件类型着色，面积 = 大小占比 |
| 🔍 逐层下钻 | 点击目录块进入子目录，面包屑导航可返回任意层级 |
| 📋 大文件排行 | Top N 大文件列表，支持打开文件所在位置 |
| 📈 类型统计 | 按扩展名分组，饼图 + 列表展示空间占用分布 |
| ⚡ 分批写入 | 扫描过程分批写入数据库，前端实时轮询进度 |
| 🚫 容错扫描 | 权限不足、路径过长等错误记录到 scan_errors 表，不中断扫描 |

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动（浏览器自动打开）
python start.py

# 3. 手动访问
# http://127.0.0.1:8765
```

## 运行测试

```bash
pip install -r requirements.txt   # 包含 pytest / httpx
pytest tests/test_smoke.py -v
```

## 项目结构

```
disk-manager/
├── backend/
│   ├── server.py              # FastAPI 入口 + open-explorer 端点
│   ├── config.py              # 配置（端口、数据库路径、颜色映射）
│   ├── core/
│   │   └── scanner.py         # 扫描引擎（生成器 + 分批 yield + 错误收集）
│   ├── models/
│   │   ├── database.py        # SQLite 异步操作层（aiosqlite）
│   │   └── schemas.py         # Pydantic 数据模型
│   ├── routers/
│   │   ├── disk.py            # GET /api/disks
│   │   ├── scan.py            # POST /api/scan, GET /api/scan/{id}, GET /api/scans
│   │   └── files.py           # GET .../files/top, GET .../files/types
│   └── services/
│       ├── scan_service.py    # 扫描业务逻辑（创建/查询/取消）
│       └── file_service.py    # 目录树 / 大文件 / 类型统计查询
├── frontend/
│   ├── index.html             # 单页应用入口
│   └── assets/
│       ├── css/style.css      # 暗色主题样式
│       └── js/
│           ├── api.js         # Fetch API 封装
│           ├── treemap.js     # ECharts TreeMap + 饼图组件
│           └── app.js         # 主应用逻辑（页面切换/轮询/渲染）
├── tests/
│   └── test_smoke.py          # 后端 smoke test（7 个用例）
├── docs/                      # 设计文档
├── start.py                   # 一键启动脚本
├── requirements.txt           # Python 依赖
└── README.md
```

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/disks` | 磁盘分区信息 |
| POST | `/api/scan` | 创建扫描任务 |
| GET | `/api/scan/{id}` | 扫描状态 + 进度 |
| DELETE | `/api/scan/{id}` | 取消扫描 |
| GET | `/api/scans` | 扫描历史列表 |
| GET | `/api/scan/{id}/tree` | 目录树（支持下钻） |
| GET | `/api/scan/{id}/files/top` | 大文件排行 |
| GET | `/api/scan/{id}/files/types` | 文件类型统计 |
| POST | `/api/open-explorer` | 在资源管理器中打开路径 |

## 技术栈

| 组件 | 技术 |
|------|------|
| 后端框架 | FastAPI + uvicorn |
| 数据库 | SQLite（aiosqlite 异步驱动） |
| 系统信息 | psutil |
| 可视化 | Apache ECharts 5.5 |
| 前端 | 原生 HTML / CSS / JS（无构建工具） |

## 设计文档

- [产品需求文档 (PRD)](docs/PRD.md)
- [技术架构](docs/ARCHITECTURE.md)
- [数据库设计](docs/DATABASE.md)
- [API 接口](docs/API.md)
- [前端 UI](docs/UI.md)
- [风险评估](docs/RISKS.md)

## 版本规划

- **V1.0** ← 当前：扫描 + TreeMap + 下钻 + 大文件 + 类型统计
- **V1.1** — 清理建议引擎 + 重复文件检测
- **V1.2** — 实时文件监控 + 趋势图 + 报告导出

## 许可证

MIT
