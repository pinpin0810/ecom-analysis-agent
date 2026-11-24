from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.common.response import PageResponse
from app.schemas.ecommerce import ProductItem
from app.models.product import Product
from app.schemas.ecommerce import OrderItem
from app.models.order import Order
from app.schemas.ecommerce import ReviewItem
from app.models.review import Review


def list_products(
    db: Session, page: int, page_size: int, keywords: str | None
) -> PageResponse:
    """分页查询商品列表"""
    query = db.query(Product)
    if keywords:
        like_str = f"%{keywords.strip()}%"
        query = query.filter(
            or_(Product.name.like(like_str), Product.category.like(like_str))
        )
    total = query.count()
    rows = (
        query.order_by(Product.create_time.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return PageResponse(
        list=[ProductItem.model_validate(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


def list_products(
    db: Session, page: int, page_size: int, keywords: str | None = None
) -> PageResponse:
    """分页查询商品列表"""
    query = db.query(Product)
    if keywords:
        like = f"%{keywords.strip()}%"
        query = query.filter(
            or_(Product.name.ilike(like), Product.category.ilike(like))
        )
    total = query.count()
    rows = (
        query.order_by(Product.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return PageResponse(
        list=[ProductItem.model_validate(row) for row in rows], total=total
    )


def list_orders(
    db: Session, page: int, page_size: int, keywords: str | None = None
) -> PageResponse:
    """分页查询订单列表"""
    query = db.query(Order, Product.name.label("product_name")).outerjoin(
        Product, Order.product_id == Product.id
    )
    if keywords:
        like = f"%{keywords.strip()}%"
        query = query.filter(
            or_(
                Order.order_no.ilike(like),
                Order.buyer_name.ilike(like),
                Product.name.ilike(like),
            )
        )
    total = query.count()
    rows = (
        query.order_by(Order.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    for order, product_name in rows:
        order.product_name = product_name
    return PageResponse(
        list=[OrderItem.model_validate(order) for order, _ in rows], total=total
    )


def list_reviews(
    db: Session, page: int, page_size: int, keywords: str | None = None
) -> PageResponse:
    """分页查询评价列表"""
    query = db.query(Review, Product.name.label("product_name")).outerjoin(
        Product, Review.product_id == Product.id
    )
    if keywords:
        like = f"%{keywords.strip()}%"
        query = query.filter(or_(Review.content.ilike(like), Product.name.ilike(like)))
    total = query.count()
    rows = (
        query.order_by(Review.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    for review, product_name in rows:
        review.product_name = product_name
    return PageResponse(
        list=[ReviewItem.model_validate(review) for review, _ in rows], total=total
    )
