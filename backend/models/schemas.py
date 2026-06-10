"""Pydantic 数据模型"""
from pydantic import BaseModel, Field
from typing import Optional


class ScanRequest(BaseModel):
    """扫描请求"""
    path: str = Field(..., description="要扫描的目录路径")
    max_depth: Optional[int] = Field(None, description="最大扫描深度")
    exclude_paths: list[str] = Field(default_factory=list, description="排除的目录路径")
    exclude_extensions: list[str] = Field(default_factory=list, description="排除的文件扩展名")
    min_file_size: int = Field(0, description="最小文件大小（字节）")


class ScanResponse(BaseModel):
    """扫描响应"""
    scan_id: int
    status: str
    message: str


class ScanStatusResponse(BaseModel):
    """扫描状态响应"""
    id: int
    root_path: str
    status: str
    total_size: int = 0
    file_count: int = 0
    dir_count: int = 0
    error_count: int = 0
    scan_duration: Optional[float] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    progress: dict = Field(default_factory=dict)


class TreeItem(BaseModel):
    """目录树子项"""
    path: str
    name: str
    is_dir: bool
    size: int = 0
    file_count: Optional[int] = None
    dir_count: Optional[int] = None
    extension: Optional[str] = None
    modified_at: Optional[str] = None
    size_percent: float = 0
    is_others: bool = False


class BreadcrumbItem(BaseModel):
    """面包屑项"""
    name: str
    path: str


class TreeResponse(BaseModel):
    """目录树响应"""
    scan_id: int
    parent_path: str
    current_path: str
    current_size: int = 0
    breadcrumb: list[BreadcrumbItem] = Field(default_factory=list)
    items: list[TreeItem] = Field(default_factory=list)
    summary: dict = Field(default_factory=dict)


class FileInfo(BaseModel):
    """文件信息"""
    path: str
    name: str
    size: int
    extension: Optional[str] = None
    modified_at: Optional[str] = None
    parent_dir: Optional[str] = None


class TopFilesResponse(BaseModel):
    """大文件排行响应"""
    total: int
    items: list[FileInfo]


class FileTypeStat(BaseModel):
    """文件类型统计"""
    extension: str
    label: str
    file_count: int
    total_size: int
    size_percent: float


class FileTypesResponse(BaseModel):
    """文件类型统计响应"""
    categories: list[FileTypeStat]
    top_extensions: list[str]
    total_size: int


class DiskPartition(BaseModel):
    """磁盘分区信息"""
    letter: str
    label: str = ""
    total_space: int
    used_space: int
    free_space: int
    usage_percent: float
    fs_type: str = ""
    mount_point: str = ""


class ApiResponse(BaseModel):
    """通用 API 响应"""
    code: int = 200
    message: str = "success"
    data: Optional[dict] = None
