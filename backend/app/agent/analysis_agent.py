"""按职责包装已有节点，只添加角色标识，不重新查询或规划。"""

from typing import Any
from app.agent import nodes
from app.agent.state import AgentState


def route(state: AgentState) -> dict[str, Any]:
    # 复用原路由判断，再给节点返回的更新字典附加角色。
    return {
        **nodes.node_route(state),
        "current_agent": "analysis",
        "agent_label": "查询分析 Agent",
    }


def structured_query(state: AgentState) -> dict[str, Any]:
    # 保留原 SQL 查询结果与失败标记，只补充角色。
    return {
        **nodes.node_structured_query(state),
        "current_agent": "analysis",
        "agent_label": "查询分析 Agent",
    }


def semantic_query(state: AgentState) -> dict[str, Any]:
    # 保留原语义检索结果，只补充角色。
    return {
        **nodes.node_semantic_query(state),
        "current_agent": "analysis",
        "agent_label": "查询分析 Agent",
    }


def judge_deepen(state: AgentState) -> dict[str, Any]:
    # 复用补充检索判断，仍由原条件边选择后续分支。
    return {
        **nodes.node_judge_deepen(state),
        "current_agent": "analysis",
        "agent_label": "查询分析 Agent",
    }


def deepen_semantic(state: AgentState) -> dict[str, Any]:
    # 复用补充评价检索，结果仍交给证据整理节点。
    return {
        **nodes.node_deepen_semantic(state),
        "current_agent": "analysis",
        "agent_label": "查询分析 Agent",
    }


def prepare_result(state: AgentState) -> dict[str, Any]:
    # 保留合并后的证据和展示结果，供后续决策与回答读取。
    return {
        **nodes.node_prepare_result(state),
        "current_agent": "analysis",
        "agent_label": "查询分析 Agent",
    }
