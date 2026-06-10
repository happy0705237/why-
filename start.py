"""DiskManager 一键启动脚本"""
import sys
import webbrowser
import threading
import time
from pathlib import Path

# 确保项目根目录在 Python 路径中
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from backend.config import HOST, PORT


def open_browser():
    """延迟打开浏览器"""
    time.sleep(1.5)
    webbrowser.open(f"http://{HOST}:{PORT}")


def main():
    print(f"""
╔══════════════════════════════════════════╗
║           DiskManager v1.0               ║
║     Windows 磁盘空间管理工具              ║
╚══════════════════════════════════════════╝

  服务地址: http://{HOST}:{PORT}
  按 Ctrl+C 停止服务
""")

    # 后台打开浏览器
    threading.Thread(target=open_browser, daemon=True).start()

    # 启动 uvicorn
    import uvicorn
    uvicorn.run(
        "backend.server:app",
        host=HOST,
        port=PORT,
        log_level="info",
        access_log=False,
    )


if __name__ == "__main__":
    main()
