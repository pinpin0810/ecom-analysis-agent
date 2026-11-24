from typing import Literal
from pydantic import BaseModel, Field


class FeedbackRequest(BaseModel):
    rating: Literal[1, -1]  # 只接受点赞或点踩，阻止其他整数进入反馈统计。
    comment: str = Field(default="", max_length=500)
