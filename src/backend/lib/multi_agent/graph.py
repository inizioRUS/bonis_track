from langgraph.graph import StateGraph, START, END

from lib.multi_agent.state import WorkflowState
from lib.llm.llm_client_open_router import LLMClient
from lib.multi_agent.tools.asana import AsanaTool
from lib.multi_agent.tools.habr import HabrTool
from lib.multi_agent.tools.retriever import RetrieverTool
from lib.multi_agent.agents.iterative_retrieval_agent.retrieval import iterative_retrieval_node
from lib.multi_agent.agents.orchestrator.orchestrator import orchestrator_node
from lib.multi_agent.agents.planner_agent.planner import planner_node
from lib.multi_agent.agents.verifier_agent.verifier import verifier_node
from lib.multi_agent.agents.writer_agent.writer import writer_node
from lib.multi_agent.agents.change_agent.change import execution_node
from lib.multi_agent.agents.memory_agent.read import memory_read_node
from lib.multi_agent.agents.memory_agent.write import memory_write_node
from lib.multi_agent.tools.memory import MemoryTool


def build_graph(
    llm: LLMClient,
    retriever_tool: RetrieverTool,
    asana_tool: AsanaTool,
    habr_tool: HabrTool,
    memory_tool: MemoryTool,
):
    graph = StateGraph(WorkflowState)

    async def execution_graph_node(state: WorkflowState):
        return await execution_node(state, asana_tool)

    async def retrieval_graph_node(state: WorkflowState):
        return await iterative_retrieval_node(
            state,
            retriever_tool,
            asana_tool,
            habr_tool,

        )

    async def planner_graph_node(state: WorkflowState):
        return await planner_node(state, llm)

    async def verifier_graph_node(state: WorkflowState):
        return await verifier_node(state, llm)

    async def writer_graph_node(state: WorkflowState):
        return await writer_node(state, llm)

    async def orchestrator_graph_node(state: WorkflowState):
        return await orchestrator_node(state)

    async def memory_read_graph_node(state: WorkflowState):
        return await memory_read_node(state, memory_tool)

    async def memory_write_graph_node(state: WorkflowState):
        return await memory_write_node(state, memory_tool, llm=llm)

    graph.add_node("execution_agent", execution_graph_node)
    graph.add_node("retrieval_agent", retrieval_graph_node)
    graph.add_node("planner_agent", planner_graph_node)
    graph.add_node("verifier_agent", verifier_graph_node)
    graph.add_node("writer_agent", writer_graph_node)
    graph.add_node("orchestrator", orchestrator_graph_node)
    graph.add_node("memory_read_agent", memory_read_graph_node)
    graph.add_node("memory_write_agent", memory_write_graph_node)

    graph.add_edge(START, "memory_read_agent")
    graph.add_edge("memory_read_agent", "planner_agent")
    graph.add_edge("retrieval_agent", "orchestrator")
    graph.add_edge("planner_agent", "orchestrator")
    graph.add_edge("verifier_agent", "orchestrator")
    graph.add_edge("execution_agent", "orchestrator")
    graph.add_edge("writer_agent", "memory_write_agent")
    graph.add_edge("memory_write_agent", END)


    def route(state: WorkflowState) -> str:
        return state["next_agent"]

    graph.add_conditional_edges(
        "orchestrator",
        route,
        {
            "retrieval_agent": "retrieval_agent",
            "planner_agent": "planner_agent",
            "verifier_agent": "verifier_agent",
            "execution_agent": "execution_agent",
            "writer_agent": "writer_agent",
            "END": END,
        },
    )

    return graph.compile()