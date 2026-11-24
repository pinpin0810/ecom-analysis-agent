"""按职责包装已有节点，只添加角色标识，不重新查询或规划。"""

from typing import Any
from app.agent import nodes
from app.agent.state import AgentState


def decide_actions(state: AgentState) -> dict[str, Any]:
    # 使用原规划逻辑读取证据，保留计划与风险判断。
    return {
        **nodes.node_decide_actions(state),
        "current_agent": "decision",
        "agent_label": "报告决策 Agent",
    }


def confirm_gate(state: AgentState) -> dict[str, Any]:
    # 原确认节点返回后才附加角色；中断时不会提前返回。
    return {
        **nodes.node_confirm_gate(state),
        "current_agent": "decision",
        "agent_label": "报告决策 Agent",
    }


def execute_actions(state: AgentState) -> dict[str, Any]:
    # 复用原执行节点，保留已提交的动作结果或取消提示。
    return {
        **nodes.node_execute_actions(state),
        "current_agent": "decision",
        "agent_label": "报告决策 Agent",
    }
