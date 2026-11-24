from functools import (
    lru_cache,
    wraps,
)  # 【新增】wraps保留被包装函数的信息；lru_cache沿用。

# 【新增】计算节点耗时、识别正常暂停，并保存节点步骤。
from time import perf_counter
from langgraph.errors import GraphInterrupt
from app.observability import service as obs_service
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from app.agent import (
    nodes,
    analysis_agent,
    decision_agent,
    scheduler,
)  # 【新增】三个角色模块，保留 nodes。
from app.agent.state import AgentState


# 【新增】包装原节点，在正常返回或异常退出时记录节点名和耗时。
def record_node(name, func):
    @wraps(func)
    def wrapped(state: AgentState):
        started = perf_counter()
        try:
            result = func(state)
        except GraphInterrupt:
            # 暂停是控制流，不是节点失败；恢复后再记录本节点成功耗时。
            raise
        except Exception as exc:
            # 只有关联了持久化运行的调用才保存步骤，异常仍向外传播。
            if state.get("run_id"):
                obs_service.record_step(
                    state["run_id"],
                    name,
                    int((perf_counter() - started) * 1000),
                    success=False,
                    detail={"exception": type(exc).__name__},
                )
            raise
        # 正常返回只记录角色和字段名，不复制整份图状态。
        if state.get("run_id"):
            obs_service.record_step(
                state["run_id"],
                name,
                int((perf_counter() - started) * 1000),
                detail={"role": result.get("agent_label"), "keys": list(result)},
            )
        return result

    return wrapped


def build_analysis_graph():
    # 节点共享问题、查询结果和证据，不在状态中传递数据库会话。
    builder = StateGraph(AgentState)
    # 【新增】为既有节点套上记录包装器，节点名称与执行边保持原值。
    builder.add_node(
        "scheduler_start",
        record_node("scheduler_start", scheduler.node_scheduler_start),
    )
    builder.add_node(
        "scheduler_handoff",
        record_node("scheduler_handoff", scheduler.node_scheduler_handoff),
    )
    builder.add_node(
        "route_question", record_node("route_question", analysis_agent.route)
    )
    builder.add_node(
        "structured_query",
        record_node("structured_query", analysis_agent.structured_query),
    )
    builder.add_node(
        "semantic_query", record_node("semantic_query", analysis_agent.semantic_query)
    )
    builder.add_node(
        "judge_deepen", record_node("judge_deepen", analysis_agent.judge_deepen)
    )
    builder.add_node(
        "deepen_semantic",
        record_node("deepen_semantic", analysis_agent.deepen_semantic),
    )
    builder.add_node(
        "prepare_result", record_node("prepare_result", analysis_agent.prepare_result)
    )
    builder.add_node(
        "decide_actions", record_node("decide_actions", decision_agent.decide_actions)
    )
    builder.add_node(
        "confirm_gate", record_node("confirm_gate", decision_agent.confirm_gate)
    )
    builder.add_node(
        "execute_actions",
        record_node("execute_actions", decision_agent.execute_actions),
    )
    # 【新增】入口先经过调度节点，再进入原有路由。
    builder.add_edge(START, "scheduler_start")
    builder.add_edge("scheduler_start", "route_question")
    builder.add_conditional_edges(
        "route_question",
        nodes.select_query_branch,
        {"sql": "structured_query", "semantic": "semantic_query"},
    )
    # SQL 阶段结束后统一判断；失败、统计问题或非评价明细会跳过补充。
    builder.add_edge("structured_query", "judge_deepen")
    # 判断函数只返回分支键，映射决定进入补充检索还是直接整理证据。
    builder.add_conditional_edges(
        "judge_deepen",
        nodes.select_after_judge,
        {"deepen": "deepen_semantic", "prepare": "prepare_result"},
    )
    # 补充检索和直接语义检索汇入同一节点，统一过滤、去重和合并来源。
    builder.add_edge("deepen_semantic", "prepare_result")
    builder.add_edge("semantic_query", "prepare_result")
    # 【新增】在证据整理与动作规划之间插入调度交接。
    # 图暂停或结束后，由对话服务根据同一份证据生成流式回答。
    builder.add_edge("prepare_result", "scheduler_handoff")
    builder.add_edge("scheduler_handoff", "decide_actions")
    builder.add_edge("decide_actions", "confirm_gate")
    builder.add_edge("confirm_gate", "execute_actions")
    builder.add_edge("execute_actions", END)
    # 编译得到可执行图，供对话服务通过 stream() 驱动节点并读取更新。
    return builder.compile(checkpointer=InMemorySaver())


@lru_cache(maxsize=1)
def get_analysis_graph():
    return build_analysis_graph()
