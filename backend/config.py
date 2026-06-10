"""DiskManager 配置管理"""
import os
from pathlib import Path

# 服务配置
HOST = "127.0.0.1"
PORT = 8765

# 数据库配置
DATA_DIR = Path.home() / ".diskmanager"
# 支持环境变量覆盖（测试时可设为 :memory:）
_db_override = os.environ.get("DISKMANAGER_DB")
DB_PATH = _db_override if _db_override else str(DATA_DIR / "data.db")

# 扫描配置
MAX_SCAN_DEPTH = 20
SCAN_TIMEOUT = 300  # 秒
MAX_WORKERS = 4
BATCH_SIZE = 5000  # 批量写入数据库的批次大小

# TreeMap 配置
TOP_ITEMS_LIMIT = 50  # 每层最多展示的子项数

# 排除的系统目录（Windows）
DEFAULT_EXCLUDE_PATHS = [
    "C:\\$Recycle.Bin",
    "C:\\System Volume Information",
    "C:\\Windows",
]

# 文件类型颜色映射（用于 TreeMap）
FILE_TYPE_COLORS = {
    "video": "#EF4444",      # 红色 - 视频
    "image": "#F59E0B",      # 琥珀色 - 图片
    "audio": "#8B5CF6",      # 紫色 - 音频
    "document": "#3B82F6",   # 蓝色 - 文档
    "archive": "#10B981",    # 绿色 - 压缩包
    "code": "#06B6D4",       # 青色 - 代码
    "executable": "#EC4899", # 粉色 - 可执行文件
    "other": "#6B7280",      # 灰色 - 其他
    "directory": "#6366F1",  # 靛蓝色 - 目录
}

# 扩展名到类型映射
EXTENSION_TYPE_MAP = {
    # 视频
    "mp4": "video", "avi": "video", "mkv": "video", "mov": "video",
    "wmv": "video", "flv": "video", "webm": "video", "m4v": "video",
    "mpg": "video", "mpeg": "video", "3gp": "video",
    # 图片
    "jpg": "image", "jpeg": "image", "png": "image", "gif": "image",
    "bmp": "image", "svg": "image", "webp": "image", "ico": "image",
    "tiff": "image", "tif": "image", "heic": "image", "heif": "image",
    # 音频
    "mp3": "audio", "wav": "audio", "flac": "audio", "aac": "audio",
    "ogg": "audio", "wma": "audio", "m4a": "audio", "opus": "audio",
    # 文档
    "pdf": "document", "doc": "document", "docx": "document",
    "xls": "document", "xlsx": "document", "ppt": "document",
    "pptx": "document", "txt": "document", "rtf": "document",
    "csv": "document", "md": "document", "odt": "document",
    # 压缩包
    "zip": "archive", "rar": "archive", "7z": "archive",
    "tar": "archive", "gz": "archive", "bz2": "archive",
    "xz": "archive", "iso": "archive",
    # 代码
    "py": "code", "js": "code", "ts": "code", "html": "code",
    "css": "code", "java": "code", "c": "code", "cpp": "code",
    "h": "code", "cs": "code", "go": "code", "rs": "code",
    "rb": "code", "php": "code", "swift": "code", "kt": "code",
    "json": "code", "xml": "code", "yaml": "code", "yml": "code",
    "sql": "code", "sh": "code", "bat": "code", "ps1": "code",
    # 可执行文件
    "exe": "executable", "msi": "executable", "dll": "executable",
    "sys": "executable", "com": "executable", "bat": "executable",
    "cmd": "executable", "ps1": "executable",
}

# 文件类型中文标签
FILE_TYPE_LABELS = {
    "video": "视频文件",
    "image": "图片文件",
    "audio": "音频文件",
    "document": "文档文件",
    "archive": "压缩包",
    "code": "代码文件",
    "executable": "可执行文件",
    "other": "其他文件",
    "directory": "目录",
}


def ensure_data_dir():
    """确保数据目录存在"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def get_file_type(extension: str | None) -> str:
    """根据扩展名返回文件类型"""
    if not extension:
        return "other"
    return EXTENSION_TYPE_MAP.get(extension.lower().lstrip("."), "other")


def get_file_color(extension: str | None, is_dir: bool = False) -> str:
    """获取文件对应的 TreeMap 颜色"""
    if is_dir:
        return FILE_TYPE_COLORS["directory"]
    file_type = get_file_type(extension)
    return FILE_TYPE_COLORS.get(file_type, FILE_TYPE_COLORS["other"])
