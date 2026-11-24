from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    # 对话服务提供问题和商品名，路由节点写入查询方式与理由。
    question: str
    product_names: list[str]
    route: str
    kind: str
    route_reason: str

    # 分开保存查询结果，防止补充检索覆盖 SQL 数据和截断标记。
    sql: str
    structured_rows: list[dict[str, Any]]
    semantic_rows: list[dict[str, Any]]
    truncated: bool
    # query_failed 标记两次 SQL 执行均失败；aggregate_intent 只用于选择失败提示。
    query_failed: bool
    aggregate_intent: bool

    # review_fields 将评价字段映射为 SQL 输出列名，供节点读取评价编号、商品编号、评分和正文。
    review_fields: dict[str, str]
    target_product_ids: list[int]
    need_deepen: bool
    # 整理节点产出统一证据和前端表格，供模型回答与 SSE 使用。
    evidence: list[dict[str, Any]]
    result: dict[str, Any]
    # 【新增】保存动作计划、确认需求和按商品统计的低分条数。
    pending_actions: list[dict[str, Any]]
    risk_level: str
    need_human_confirm: bool
    low_rating_counts: dict[str, int]
    decide_reason: str
    # 【新增】绑定本轮用户，恢复时校验归属；thread_id由调用配置提供。
    user_id: int
    # 【新增】保存确认结果，供后续动作执行判断是否跳过。
    human_approved: bool
    # 【新增】保存选择处理结果，由确认接口返回并显示在对应轮次。
    status_message: str
    # 【新增】白名单执行器成功提交后返回的报告/预警编号或复核状态。
    actions_executed: list[dict[str, Any]]
    # 【新增】把数据库运行编号写入检查点，确认恢复继续追加同一运行的步骤。
    run_id: int
