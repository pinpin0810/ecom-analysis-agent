from fastapi import APIRouter
from app.api.auth import router as auth_router
from app.api.user import router as user_router
from app.api.files import router as files_router
from app.api.ecommerce import router as ecommerce_router
from app.api.chat import router as chat_router

# 【新增】将运行观测接口挂到已有/api入口。
from app.api import observability

api = APIRouter(prefix="/api")

api.include_router(auth_router)
api.include_router(user_router)
api.include_router(ecommerce_router)
api.include_router(files_router)
api.include_router(chat_router)
api.include_router(observability.router)
