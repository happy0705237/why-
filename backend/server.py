"""FastAPI 应用入口"""
import os
import subprocess
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from backend.routers import disk, scan, files
from backend.models.database import close_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    yield
    # 关闭数据库连接
    await close_db()


app = FastAPI(
    title="DiskManager",
    description="Windows 磁盘空间管理工具",
    version="1.0.1",
    lifespan=lifespan,
)

# 注册路由
app.include_router(disk.router)
app.include_router(scan.router)
app.include_router(files.router)

# 静态文件目录
frontend_dir = Path(__file__).parent.parent / "frontend"
app.mount("/assets", StaticFiles(directory=str(frontend_dir / "assets")), name="assets")


@app.get("/")
async def index():
    """首页"""
    return FileResponse(str(frontend_dir / "index.html"))


class OpenExplorerRequest(BaseModel):
    path: str


@app.post("/api/open-explorer")
async def open_explorer(req: OpenExplorerRequest):
    """在 Windows 资源管理器中打开路径"""
    try:
        path = req.path
        if os.path.exists(path):
            if os.path.isfile(path):
                subprocess.Popen(["explorer", "/select,", path])
            else:
                subprocess.Popen(["explorer", path])
            return {"code": 200, "message": "ok"}
        return {"code": 404, "message": "路径不存在"}
    except Exception as e:
        return {"code": 500, "message": str(e)}
