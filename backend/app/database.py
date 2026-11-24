from sqlalchemy.orm import sessionmaker, DeclarativeBase, Mapped, mapped_column
from sqlalchemy import create_engine, DateTime
from app.config import settings
from datetime import datetime

engine = create_engine(settings.DATA_BASE_URL)

# 数据库session会话的连接工厂
SessionLocal = sessionmaker(bind=engine, autoflush=False)

# A if 条件 else B 是条件表达式：配置存在时创建引擎，否则使用 None。
# 未配置时不建查询引擎，让已有业务页面仍能启动。
query_engine = (
    create_engine(settings.QUERY_DATA_BASE_URL, pool_pre_ping=True)
    if settings.QUERY_DATA_BASE_URL
    else None
)
# pool_pre_ping 在借出连接时检查可用性，不代表 SQL 的执行超时。
QuerySessionLocal = sessionmaker(bind=query_engine, autoflush=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class Base(DeclarativeBase):
    id: Mapped[int] = mapped_column(
        primary_key=True, autoincrement=True, comment="主键ID", sort_order=-1
    )
    create_time: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, comment="创建时间"
    )
    update_time: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间"
    )
