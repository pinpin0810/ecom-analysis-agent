from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # 后端项目的根路径


class Settings(BaseSettings):
    DATA_BASE_URL: str
    # 与业务连接分开，只用于受限的模型查询（只读用户）。
    QUERY_DATA_BASE_URL: str = ""

    JWT_SECRET_KEY: str
    JWT_EXPIRE_HOURS: int = 24
    JWT_ALGORITHM: str = "HS256"
    # 向量（Qwen3.7-通用文本向量-qwen3.7-text-embedding）
    LLM_BASE_URL: str = "https://api.deepseek.com"
    LLM_API_KEY: str
    LLM_MODEL: str
    LLM_TIMEOUT_SECONDS: float = 60  # 为一次模型请求设置 60 秒的网络超时时间
    # 向量
    EMBEDDING_BASE_URL: str = ""
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_MODEL: str = ""
    EMBEDDING_TIMEOUT_SECONDS: float = 15.0  # 限制网络等待，避免长时间无反馈。
    # chroma向量数据库
    CHROMA_PERSIST_DIR: str = "data/chroma"
    CHROMA_COLLECTION: str = "ecom_texts"
    CORS_ORIGINS: str = "http://localhost:5174,http://127.0.0.1:5174"

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env", env_file_encoding="utf-8"
    )


settings = Settings()

# 相对路径以 backend 为基准，避免从不同工作目录启动时读取不同索引。
CHROMA_DIR = BASE_DIR / settings.CHROMA_PERSIST_DIR

UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100M


ALLOWED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".zip",
}
