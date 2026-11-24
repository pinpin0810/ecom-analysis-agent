from app.common.response import Response
from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.services import (
    ecommerce_service,
    diagnosis_service,
)  # 【新增】diagnosis_service 处理报告与预警。
from sqlalchemy.orm import Session

from typing_extensions import Annotated
from fastapi import APIRouter, Depends, Query

router = APIRouter(prefix="/ecommerce", tags=["商品相关的API接口"])


@router.get("/products")
def get_products(
    _user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 10,
    keywords: str | None = None,
):
    """获取商品列表"""
    page_result = ecommerce_service.list_products(db, page, page_size, keywords)
    return Response.success(data=page_result.model_dump())


@router.get("/orders")
def get_orders(
    _user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 10,
    keywords: str | None = None,
):
    """获取订单列表"""
    page_result = ecommerce_service.list_orders(db, page, page_size, keywords)
    return Response.success(data=page_result.model_dump())


@router.get("/reviews")
def get_reviews(
    _user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 10,
    keywords: str | None = None,
):
    """获取评论列表"""
    page_result = ecommerce_service.list_reviews(db, page, page_size, keywords)
    return Response.success(data=page_result.model_dump())


# 【新增】为本人报告与预警提供列表、汇总及已读接口。
@router.get("/reports")
def list_reports(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 10,
    keywords: str | None = None,
):
    # 只传入认证得到的用户编号，搜索与分页不能扩大记录归属范围。
    return Response.success(
        data=diagnosis_service.list_records(
            db, current_user.id, "reports", page, page_size, keywords
        )
    )


@router.get("/alerts")
def list_alerts(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 10,
    keywords: str | None = None,
):
    return Response.success(
        data=diagnosis_service.list_records(
            db, current_user.id, "alerts", page, page_size, keywords
        )
    )


@router.get("/alerts/summary")
def alert_summary(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    return Response.success(
        data=diagnosis_service.get_alert_summary(db, current_user.id)
    )


@router.post("/alerts/read-all")
def read_all_alerts(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    # 批量已读只按本人范围执行，不接收当前页编号或搜索词。
    return Response.success(
        data=diagnosis_service.mark_all_alerts_read(db, current_user.id)
    )


@router.post("/alerts/{alert_id}/read")
def read_alert(
    alert_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    return Response.success(
        data=diagnosis_service.mark_alert_read(db, current_user.id, alert_id)
    )
