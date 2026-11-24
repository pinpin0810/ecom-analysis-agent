from decimal import Decimal
from unicodedata import category

from sqlalchemy import Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Product(Base):
    """商品表"""

    __tablename__ = "products"
    __tableargs__ = {"comment": "商品信息表"}

    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="商品名称")
    category: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="商品分类"
    )
    description: Mapped[str | None] = mapped_column(
        Text, nullable=False, comment="商品描述"
    )
    price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, comment="商品价格"
    )
    stock: Mapped[int] = mapped_column(nullable=False, default=0, comment="商品库存")
    # on_sale 上架  off_sale 下架
    shelf_status: Mapped[bool] = mapped_column(
        String(20),
        nullable=False,
        default="on_sale",
        comment="商品上下架状态",
    )
    # normal 正常  pending_review 待人工审核
    review_status: Mapped[bool] = mapped_column(
        String(20),
        nullable=False,
        default="normal",
        comment="人工复核状态",
    )
