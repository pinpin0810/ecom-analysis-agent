from fastapi.responses import StreamingResponse
from typing_extensions import Annotated

from fastapi import APIRouter, Depends

from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.chat import ChatRequest
from app.services import chat_service
from app.schemas.chat import (
    ChatRequest,
    ConfirmRequest,
)  # 【新增】ConfirmRequest 校验确认请求。
from app.services import (
    chat_service,
    confirmation_service,
)  # 【新增】confirmation_service 恢复原图。
from app.common.response import Response  # 【新增】返回统一响应。

router = APIRouter(prefix="/chat", tags=["AI对话"])


@router.post("/stream")
def chat_stream(
    body: ChatRequest, current_user: Annotated[User, Depends(get_current_user)]
):
    """认证负责身份，history 只提供本轮查询的上下文。"""
    return StreamingResponse(
        chat_service.stream_chat(
            question=body.question,
            user_id=current_user.id,
            history=[turn.model_dump() for turn in body.history],
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# 【新增】以当前登录身份提交选择，不接收请求体中的用户编号。
@router.post("/actions/confirm")
def confirm_actions(
    body: ConfirmRequest, current_user: Annotated[User, Depends(get_current_user)]
):
    result = confirmation_service.resume_actions(
        body.thread_id, body.approved, current_user.id
    )
    return Response.success(data=result)
