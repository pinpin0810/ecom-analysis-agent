from datetime import date, datetime
from decimal import Decimal
import json
import logging
from time import perf_counter
from typing import Any
import re
from collections import Counter
from math import isfinite
from langgraph.types import interrupt  # 【新增】在确认节点暂停并接收恢复选择。

from sqlglot import exp, parse_one
from langgraph.config import get_stream_writer
from openai import APIError

from app.agent.state import AgentState
from app.database import QuerySessionLocal, query_engine
from app.services import nl2sql_service, query_router_service, semantic_service
from app.services import action_decision  # 【新增】调用动作规划模块
from app.database import SessionLocal  # 【新增】为动作执行创建数据库会话。
from app.services import action_service  # 【新增】通过模块调用白名单执行器。

logger = logging.getLogger(__name__)

# 同一商品至少有两条不同的低分评价才触发补充检索，不跨商品累计。
LOW_RATING_THRESHOLD = 2
# 过滤相似度低于该阈值的语义候选，保留 SQL 查询结果。
MIN_SIMILARITY = 0.35
# 仅在 SQL 执行失败时辅助选择统计失败提示，不决定明细是否补充检索。
AGGREGATE_PATTERN = re.compile(
    r"统计|数量|总数|总计|总共|合计|平均|排名|占比|"
    r"多少\s*(?:个|条|笔|件|评价|评论|订单|商品|产品)|几\s*[个条笔件]|销量|销售额|趋势"
)


# 检查评价编号、商品编号、评分和正文是否来自 reviews，再记录各自的输出列名。
def _review_fields(sql: str) -> dict[str, str]:
    query = parse_one(sql, read="mysql")
    # 聚合、分组与去重查询不视为逐条评价明细。
    if (
        query.args.get("group")
        or query.args.get("distinct")
        or any(query.find_all(exp.AggFunc))
    ):
        return {}
    # 含子查询时返回空映射，避免把内层表别名当成外层评价字段的来源。
    if any(query.find_all(exp.Subquery)):
        return {}
    tables = list(query.find_all(exp.Table))
    review_tables = [table for table in tables if table.name.lower() == "reviews"]
    # 必须且只能出现一个 reviews 表实例，否则无法确认四个字段属于同一条评价。
    if len(review_tables) != 1:
        return {}
    aliases = {table.alias_or_name.lower() for table in review_tables}
    fields = {}
    for projection in query.expressions:
        column = projection.this if isinstance(projection, exp.Alias) else projection
        # 跳过表达式和常量，只从直接输出的列中识别评价字段。
        if not isinstance(column, exp.Column):
            continue
        # 有别名时核对所属表；无别名时只接受单表评价查询。
        from_review = column.table.lower() in aliases or (
            not column.table
            and len(tables) == 1
            and tables[0].name.lower() == "reviews"
        )
        # 记录 id、product_id、rating、content 对应的输出列名，供后续读取结果行。
        if from_review and column.name.lower() in {
            "id",
            "product_id",
            "rating",
            "content",
        }:
            fields[column.name.lower()] = projection.alias_or_name
    # 四个字段全部找到才返回映射；缺少任意字段时保留 SQL 结果并跳过补充检索。
    return fields if len(fields) == 4 else {}


# 保存执行后的 SQL、原始结果和截断标记；两次执行均失败时设置 query_failed。
def node_structured_query(state: AgentState) -> dict[str, Any]:
    _progress("structured_query", "正在生成、校验并执行 SQL…")
    aggregate_intent = bool(AGGREGATE_PATTERN.search(state["question"]))
    try:
        sql, rows, truncated = nl2sql_service.query_by_question(state["question"])
    except nl2sql_service.QueryExecutionError:
        # 两次 SQL 执行均失败时返回失败状态；配置、校验和模型调用异常继续向外抛出。
        logger.exception("SQL 修复后仍失败")
        return {
            "sql": "",
            "structured_rows": [],
            "semantic_rows": [],
            "truncated": False,
            "query_failed": True,
            "aggregate_intent": aggregate_intent,
            "review_fields": {},
        }
    return {
        "sql": sql,
        "structured_rows": rows,
        "semantic_rows": [],
        "truncated": truncated,
        "query_failed": False,
        "aggregate_intent": aggregate_intent,
        "review_fields": _review_fields(sql),
    }


def _progress(node: str, message: str) -> None:
    """在节点内发送进度，由对话服务转换为 SSE 状态事件。"""
    # 使用当前图执行的 custom 消息通道，不将进度写入查询状态。
    writer = get_stream_writer()
    # 【新增】role 标明运行中进度的所属角色，node 与 message 沿用原值。
    writer({"node": node, "role": "查询分析 Agent", "message": message})


def node_route(state: AgentState) -> dict[str, Any]:
    # 复用已有路由规则，并将决策转换为后续节点共用的状态字段。
    decision = query_router_service.decide_query_route(
        state["question"], state["product_names"]
    )
    return {
        "route": decision["route"],
        "kind": decision["kind"],
        "route_reason": decision["reason"],
    }


def select_query_branch(state: AgentState) -> str:
    """返回条件边的分支键，不在这里执行查询。"""
    return state["route"]


# 第14节课要求删除此方法，暂时注释
# def node_structured_query(state: AgentState) -> dict[str, Any]:
#     _progress("structured_query", "正在生成 SQL 查询…")
#     try:
#         started = perf_counter()
#         sql = nl2sql_service.generate_sql(state["question"])
#         logger.info("生成 SQL 耗时：%.2f 秒", perf_counter() - started)
#         logger.info("模型生成的 SQL：%s", sql)
#     except ValueError:
#         # 裸 raise 重新抛出当前异常，保留具体提示，避免被后面的通用分支改写。
#         raise
#     except APIError as exc:
#         # 模型接口异常转换为可展示的提示，同时保留原异常链。
#         raise ValueError("大模型调用失败，请检查服务地址、模型状态和 API 余额") from exc
#     except Exception as exc:
#         raise ValueError("生成 SQL 失败，请稍后重试") from exc

#     _progress("structured_query", "SQL 已生成，正在校验并执行只读查询…")
#     # 查询连接未配置时立即结束，不能改用普通业务连接执行模型 SQL。
#     if query_engine is None:
#         raise ValueError("请配置只读查询数据库连接")

#     try:
#         # 仅使用只读查询连接；退出 with 时关闭会话，包括异常路径。
#         with QuerySessionLocal() as db:
#             started = perf_counter()
#             safe_sql, rows, truncated = nl2sql_service.execute_select(db, sql)
#             logger.info("SQL 校验与执行耗时：%.2f 秒", perf_counter() - started)
#     except ValueError:
#         # 裸 raise 重新抛出当前异常，保留具体提示，避免被后面的通用分支改写。
#         raise
#     except Exception as exc:
#         raise ValueError("执行查询操作异常，请稍后重试") from exc

#     # 保存校验器返回的最终执行语句，供页面展示和核对。
#     return {"sql": safe_sql, "rows": rows, "truncated": truncated}


def node_semantic_query(state: AgentState) -> dict[str, Any]:
    # 路由节点已确定检索商品还是评价，不在查询节点重新判断。
    kind = state["kind"]
    kind_label = {"product": "商品", "review": "评价"}[kind]
    _progress("semantic_query", f"正在进行{kind_label}语义检索并回查原文…")
    try:
        # 服务内部完成向量检索和数据库原文回查。
        rows = semantic_service.search_records(state["question"], kind)
    except ValueError:
        # 裸 raise 重新抛出当前异常，保留具体提示，避免被后面的通用分支改写。
        raise
    except Exception as exc:
        raise ValueError("语义检索失败，请检查后端日志和索引设置") from exc

    # 空 SQL 隐藏执行语句区域；False 仅表示不用 SQL 截断提示，不代表召回全部记录。
    return {"sql": "", "rows": rows, "truncated": False}


def _json_value(value: Any) -> str:
    """将查询中的金额和日期转换为 JSON 可传输的字符串。"""
    # 金额保留十进制文本，避免转为浮点数后丢失精度。
    if isinstance(value, Decimal):
        return str(value)
    # datetime 也是 date 的子类，先处理它以保留时分秒。
    if isinstance(value, datetime):
        return value.isoformat(sep=" ")
    # 纯日期只输出年月日；其他未知类型继续报错，避免静默改写数据。
    if isinstance(value, date):
        return value.isoformat()
    raise TypeError("不支持的查询结果类型")


# 第14节课要求删除此方法，暂时注释
# def node_prepare_result(state: AgentState) -> dict[str, Any]:
#     rows = state["rows"]
#     # 空结果没有首行，列名使用空列表；往返 JSON 将金额和日期转换为可传输值。
#     result = {
#         "sql": state["sql"],
#         "columns": list(rows[0]) if rows else [],
#         "rows": json.loads(json.dumps(rows, ensure_ascii=False, default=_json_value)),
#         "truncated": state["truncated"],
#     }
#     # 两条路径共用表格结构，但摘要分别说明 SQL 行数和语义候选数量。
#     if state["route"] == "semantic":
#         summary = (
#             f"找到 {len(rows)} 条相似的语义结果"
#             f"（最多展示 {semantic_service.TOP_K} 条，请结合原文判断）"
#         )
#     else:
#         # SQL 聚合也可能只返回一行，摘要不把结果行数当作业务统计值。
#         summary = f"查询完成，共查询到 {len(rows)} 行；统计值请查看表格。"
#         # 取满查询上限只说明可能还有记录，不能断言已确认存在下一行。
#         if state["truncated"]:
#             summary += " 已达到查询行数上限，可能还有更多记录。"
#     return {"result": result, "summary": summary}


# 按评价编号去重，再按商品统计评分不超过 2 分的评价，选出需要补充检索的商品。
def node_judge_deepen(state: AgentState) -> dict[str, Any]:
    fields = state.get("review_fields", {})
    # 失败或未确认评价明细时跳过；聚合结果已被列来源检查排除。
    if state.get("query_failed") or not fields:
        return {"need_deepen": False, "target_product_ids": []}
    # 空评价编号代表未关联到评价，不计数；其余按评价编号去重。
    reviews = {
        row[fields["id"]]: row
        for row in state["structured_rows"]
        if row[fields["id"]] is not None
    }
    # 缺少商品或评分的行不计入，低分按 rating <= 2 判断。
    counts = Counter(
        int(row[fields["product_id"]])
        for row in reviews.values()
        if row[fields["product_id"]] is not None
        and row[fields["rating"]] is not None
        and int(row[fields["rating"]]) <= 2
    )
    # 只保留低分评价条数达到阈值的商品，按商品编号升序排列。
    targets = sorted(
        pid for pid, count in counts.items() if count >= LOW_RATING_THRESHOLD
    )
    _progress("judge_deepen", f"满足补充条件的商品数：{len(targets)}")
    return {"need_deepen": bool(targets), "target_product_ids": targets}


def select_after_judge(state: AgentState) -> str:
    # 只返回条件边的分支键，由图选择下一节点，不在这里执行检索。
    return "deepen" if state["need_deepen"] else "prepare"


# 只检索 target_product_ids 中商品的评价，不扩大为全库检索。
def node_deepen_semantic(state: AgentState) -> dict[str, Any]:
    targets = state["target_product_ids"]
    # 没有明确商品范围就跳过，不能将空列表改成 None 后查询全库。
    if not targets:
        return {"semantic_rows": []}
    _progress("deepen_semantic", "正在检索相关商品的补充评价…")
    rows = semantic_service.search_records(
        state["question"], "review", product_ids=targets
    )
    return {"semantic_rows": rows}


# 直接语义分支按 kind 检索商品或评价，不经过 SQL 补充判断。
def node_semantic_query(state: AgentState) -> dict[str, Any]:
    _progress("semantic_query", "正在进行语义检索并回查原文…")
    rows = semantic_service.search_records(state["question"], state["kind"])
    return {
        "sql": "",
        "structured_rows": [],
        "semantic_rows": rows,
        "truncated": False,
        "query_failed": False,
        "review_fields": {},
        "target_product_ids": [],
        "need_deepen": False,
    }


# 以 SQL 结果为基础合并候选，产出统一证据和前端表格。
def node_prepare_result(state: AgentState) -> dict[str, Any]:
    evidence = []
    # 仅用评价编号建立去重映射，商品与订单编号不参与此映射。
    reviews = {}
    fields = state.get("review_fields", {})
    for row in state.get("structured_rows", []):
        item = {**row, "sources": ["sql"], "evidence_type": "sql_result"}
        # 只有非空评价编号才确认评价身份；外连接未命中的行保留原样，不参与去重。
        if fields and row[fields["id"]] is not None:
            item.update(
                {
                    "review_id": row[fields["id"]],
                    "product_id": row[fields["product_id"]],
                    "rating": row[fields["rating"]],
                    "content": row[fields["content"]],
                    "evidence_type": "review",
                }
            )
            key = item["review_id"]
            # 关联查询重复返回同一评价时，只保留首次出现的记录。
            if key in reviews:
                continue
            reviews[key] = item
        evidence.append(item)

    targets = state.get("target_product_ids", [])
    for row in state.get("semantic_rows", []):
        similarity = float(row["similarity"])
        # 丢弃相似度为非有限数或低于 MIN_SIMILARITY 的候选，已保留的 SQL 行不受影响。
        if not isfinite(similarity) or similarity < MIN_SIMILARITY:
            continue
        # MySQL 回查后的评价若已不属于目标商品，就丢弃，避免使用过期索引关联。
        if state["route"] == "sql" and row.get("product_id") not in targets:
            continue
        # SQL 补充只查评价，直接语义分支则按 kind 区分商品和评价。
        is_review = state["route"] == "sql" or state["kind"] == "review"
        item = {**row, "sources": ["semantic"], "evidence_type": "product"}
        # 商品候选保留商品身份，只有评价才按 review_id 去重、合并来源。
        if is_review:
            item.update({"review_id": row["id"], "evidence_type": "review"})
            existing = reviews.get(item["review_id"])
            # 已存在的评价不再追加，仅补充 semantic 来源和相似度，保留原字段与排列位置。
            if existing is not None:
                existing["sources"] = list(
                    dict.fromkeys(existing["sources"] + ["semantic"])
                )
                existing["similarity"] = similarity
                continue
            reviews[item["review_id"]] = item
        evidence.append(item)

    # 收集所有证据的列名并去重，让仅在后续行出现的字段也能显示在表格中。
    columns = list(dict.fromkeys(key for row in evidence for key in row))
    result = {
        "sql": state.get("sql", ""),
        "columns": columns,
        "rows": evidence,
        "truncated": state["truncated"],
    }
    # 使用 _json_value 将金额和日期转换为字符串，让模型输入与 SSE 结果都可序列化。
    result = json.loads(json.dumps(result, ensure_ascii=False, default=_json_value))
    return {"evidence": result["rows"], "result": result}


# 【新增】将动作规则返回的字段写入图状态。
def node_decide_actions(state: AgentState) -> dict[str, Any]:
    # 使用整理后的同一份证据，避免直接把未过滤的语义候选送进规则。
    return action_decision.decide_actions(state)


# 【新增】将高风险计划暂停，或把低风险计划直接标为允许执行。
def node_confirm_gate(state: AgentState) -> dict[str, Any]:
    # 只有报告或无动作时无需暂停，后续仍使用同一出口接执行节点。
    if not state.get("need_human_confirm"):
        return {"human_approved": True, "status_message": "低风险计划，无需人工确认"}
    # 恢复时节点会从头执行，interrupt之前只组装数据，不能写库或发通知。
    decision = interrupt(
        {
            "message": "请确认是否执行以下动作",
            "risk_level": state["risk_level"],
            "reason": state["decide_reason"],
            "actions": state["pending_actions"],
        }
    )
    approved = isinstance(decision, dict) and decision.get("approved") is True
    return {
        "human_approved": approved,
        "status_message": (
            "计划已确认，尚未写入业务数据" if approved else "用户已取消，跳过动作"
        ),
    }


# 【新增】读取批准结果和待执行计划，写回已提交的动作结果。
def node_execute_actions(state: AgentState) -> dict[str, Any]:
    actions = state.get("pending_actions", [])
    # 取消时跳过整组动作，包括报告，不能仅跳过其中的预警。
    if not state.get("human_approved") or not actions:
        return {"actions_executed": [], "status_message": "未执行动作"}
    context = {
        "question": state["question"],
        "user_id": state["user_id"],
        "route": state["route"],
        "risk_level": state["risk_level"],
        "evidence_count": len(state["evidence"]),
    }
    # 事务由执行器统一提交/回滚，节点只负责会话的创建与关闭。
    with SessionLocal() as db:
        executed = action_service.execute_actions(db, actions, context)
    return {
        "actions_executed": executed,
        "status_message": f"已执行 {len(executed)} 个动作",
    }
