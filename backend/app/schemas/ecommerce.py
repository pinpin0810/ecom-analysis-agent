from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class ProductItem(BaseModel):
    """商品只读模型"""

    id: int
    name: str
    category: str
    description: str
    price: Decimal
    stock: int
    shelf_status: str
    review_status: str
    create_time: datetime | None = None

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("price")
    def _price(self, v: Decimal) -> float:
        return float(v)

    @field_serializer("create_time")
    def _create_time(self, v: datetime | None) -> str | None:

        return v.strftime("%Y-%m-%d %H:%M:%S") if v else None  # 2026-06-24 15:00:00


class OrderItem(BaseModel):
    """订单只读模型"""

    id: int
    order_no: str
    product_id: int
    product_name: str
    buyer_name: str
    quantity: int
    amount: Decimal
    status: str
    create_time: datetime | None = None

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("amount")
    def _amount_to_float(self, v: Decimal) -> float:
        return float(v)

    @field_serializer("create_time")
    def _create_time(self, v: datetime | None) -> str | None:
        return v.strftime("%Y-%m-%d %H:%M:%S") if v else None


class ReviewItem(BaseModel):
    """评价只读模型"""

    id: int
    product_id: int
    product_name: str
    order_id: int | None = None
    rating: int
    content: str
    img: str | None = None
    create_time: datetime | None = None

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("create_time")
    def _create_time(self, v: datetime | None) -> str | None:
        return v.strftime("%Y-%m-%d %H:%M:%S") if v else None
