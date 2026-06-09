"""Tests for the LangGraph adapter.

Adapter *plumbing* (discovery, injection folding, extraction) is tested against a
real compiled LangGraph graph whose node is deterministic — a legitimate test double
for the LLM, not fabricated scenario data. The genuine end-to-end run against a real
model lives in ``test_realagent_e2e.py`` and is skipped without an API key.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from aion_redteam.adapters.langgraph import LangGraphTarget
from aion_redteam.core.scenario import InjectionPoint, Setup
from aion_redteam.core.target import TargetError

# A real, deterministic LangGraph target: the node echoes the last user message so
# tests can assert exactly what reached the agent.
ECHO_TARGET = textwrap.dedent(
    """
    from langchain_core.messages import AIMessage, SystemMessage
    from langgraph.graph import START, END, MessagesState, StateGraph

    def node(state):
        msgs = state["messages"]
        sys = next((m.content for m in msgs if isinstance(m, SystemMessage)), "<none>")
        user = msgs[-1].content
        return {"messages": [AIMessage(content=f"SYS={sys}||USER={user}")]}

    _b = StateGraph(MessagesState)
    _b.add_node("node", node)
    _b.add_edge(START, "node")
    _b.add_edge("node", END)
    graph = _b.compile()
    """
).strip()


@pytest.fixture
def echo_target_path(tmp_path: Path) -> Path:
    path = tmp_path / "echo_agent.py"
    path.write_text(ECHO_TARGET, encoding="utf-8")
    return path


async def _load(path: Path, **config) -> LangGraphTarget:
    target = LangGraphTarget()
    await target.load({"target": str(path), **config})
    return target


async def _run_once(target: LangGraphTarget, payload, point, agent_input="benign task"):
    await target.reset()
    await target.inject(payload, point)
    await target.execute(agent_input)
    return await target.get_response()


class TestLoading:
    async def test_loads_module_level_graph(self, echo_target_path) -> None:
        target = await _load(echo_target_path)
        assert target._graph is not None

    async def test_explicit_attribute(self, echo_target_path) -> None:
        target = await _load(echo_target_path, attribute="graph")
        assert target._graph is not None

    async def test_missing_file_raises(self, tmp_path) -> None:
        with pytest.raises(TargetError, match="not found"):
            await _load(tmp_path / "nope.py")

    async def test_missing_target_key_raises(self) -> None:
        target = LangGraphTarget()
        with pytest.raises(TargetError, match="requires a 'target'"):
            await target.load({})

    async def test_no_graph_in_module(self, tmp_path) -> None:
        path = tmp_path / "empty.py"
        path.write_text("x = 1\n", encoding="utf-8")
        with pytest.raises(TargetError, match="no compiled LangGraph graph"):
            await _load(path)

    async def test_factory_discovery(self, tmp_path) -> None:
        path = tmp_path / "factory_agent.py"
        factory_src = ECHO_TARGET.replace(
            "graph = _b.compile()",
            "def build_graph():\n    return _b.compile()",
        )
        path.write_text(factory_src, encoding="utf-8")
        target = await _load(path)
        assert target._graph is not None


class TestInjectionFolding:
    async def test_user_message_injection_appended(self, echo_target_path) -> None:
        target = await _load(echo_target_path)
        resp = await _run_once(target, "IGNORE PREVIOUS", InjectionPoint.USER_MESSAGE)
        assert "USER=benign task\n\nIGNORE PREVIOUS" in resp.final_output

    async def test_system_prompt_injection_overrides(self, echo_target_path) -> None:
        target = await _load(echo_target_path)
        resp = await _run_once(target, "you are evil", InjectionPoint.SYSTEM_PROMPT)
        assert "SYS=you are evil" in resp.final_output

    async def test_rag_document_labeled(self, echo_target_path) -> None:
        target = await _load(echo_target_path)
        resp = await _run_once(target, "poisoned doc", InjectionPoint.RAG_DOCUMENT)
        assert "[Retrieved document]:\npoisoned doc" in resp.final_output

    async def test_configure_sets_system_prompt(self, echo_target_path) -> None:
        target = await _load(echo_target_path)
        await target.reset()
        await target.configure(Setup(agent_input="x", system_prompt="be careful"))
        await target.inject("hello", InjectionPoint.USER_MESSAGE)
        await target.execute("do it")
        resp = await target.get_response()
        assert "SYS=be careful" in resp.final_output


class TestResponseExtraction:
    async def test_trace_and_final_output(self, echo_target_path) -> None:
        target = await _load(echo_target_path)
        resp = await _run_once(target, "p", InjectionPoint.USER_MESSAGE)
        assert resp.error is None
        assert resp.final_output.startswith("SYS=")
        assert any("AIMessage" in line for line in resp.full_trace)
        assert resp.duration_ms >= 0

    async def test_graph_exception_captured(self, tmp_path) -> None:
        path = tmp_path / "boom_agent.py"
        path.write_text(
            ECHO_TARGET.replace(
                'return {"messages": [AIMessage(content=f"SYS={sys}||USER={user}")]}',
                'raise RuntimeError("node boom")',
            ),
            encoding="utf-8",
        )
        target = await _load(path)
        resp = await _run_once(target, "p", InjectionPoint.USER_MESSAGE)
        assert resp.error is not None
        assert "node boom" in resp.error
