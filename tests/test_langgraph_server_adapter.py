"""Tests for the LangGraph Server (HTTP) adapter using a fake langgraph_sdk client."""

from __future__ import annotations

import langgraph_sdk
import pytest

from aion_redteam.adapters.langgraph_server import LangGraphServerTarget
from aion_redteam.core.scenario import InjectionPoint
from aion_redteam.core.target import TargetError


class _FakeAssistants:
    def __init__(self, assistants):
        self._assistants = assistants
        self.raise_on_search = False

    async def search(self, limit=100):
        if self.raise_on_search:
            raise ConnectionError("connection refused")
        return self._assistants


class _FakeThreads:
    async def create(self):
        return {"thread_id": "thread-1"}


class _FakeRuns:
    def __init__(self, capture, final_state):
        self._capture = capture
        self._final_state = final_state

    async def wait(self, thread_id, assistant_id, input):  # noqa: A002
        self._capture["assistant_id"] = assistant_id
        self._capture["input"] = input
        if callable(self._final_state):
            return self._final_state(input)
        return self._final_state


class _FakeClient:
    def __init__(self, assistants, capture, final_state):
        self.assistants = _FakeAssistants(assistants)
        self.threads = _FakeThreads()
        self.runs = _FakeRuns(capture, final_state)


def _install_fake(monkeypatch, *, assistants=None, final_state=None, capture=None):
    assistants = assistants if assistants is not None else [
        {"assistant_id": "aid-1", "graph_id": "agent", "name": "agent"}
    ]
    capture = capture if capture is not None else {}

    def _echo(inp):
        user = inp["messages"][-1]["content"]
        return {"messages": [{"type": "ai", "content": f"ECHO:{user}", "tool_calls": []}]}

    client = _FakeClient(assistants, capture, final_state or _echo)
    monkeypatch.setattr(langgraph_sdk, "get_client", lambda url=None, api_key=None: client)
    return client, capture


async def _loaded(monkeypatch, **kw):
    client, capture = _install_fake(monkeypatch, **kw)
    target = LangGraphServerTarget()
    await target.load({"base_url": "http://localhost:2024", "assistant": "agent"})
    return target, client, capture


class TestLoad:
    async def test_resolves_assistant_by_graph_id(self, monkeypatch) -> None:
        target, _, _ = await _loaded(monkeypatch)
        assert target._assistant_id == "aid-1"

    async def test_assistant_not_found_raises(self, monkeypatch) -> None:
        _install_fake(monkeypatch, assistants=[
            {"assistant_id": "x", "graph_id": "other", "name": "other"}
        ])
        target = LangGraphServerTarget()
        with pytest.raises(TargetError, match="not found"):
            await target.load({"base_url": "http://localhost:2024", "assistant": "agent"})

    async def test_unreachable_server_raises(self, monkeypatch) -> None:
        client, _ = _install_fake(monkeypatch)
        client.assistants.raise_on_search = True
        target = LangGraphServerTarget()
        with pytest.raises(TargetError, match="could not reach"):
            await target.load({"base_url": "http://localhost:2024"})


class TestExecute:
    async def test_user_message_injection_reaches_server(self, monkeypatch) -> None:
        target, _, capture = await _loaded(monkeypatch)
        await target.reset()
        await target.inject("EVIL PAYLOAD", InjectionPoint.USER_MESSAGE)
        await target.execute("benign task")
        resp = await target.get_response()
        sent = capture["input"]["messages"][-1]["content"]
        assert "benign task" in sent and "EVIL PAYLOAD" in sent
        assert "ECHO:benign task" in resp.final_output

    async def test_system_prompt_injection(self, monkeypatch) -> None:
        target, _, capture = await _loaded(monkeypatch)
        await target.reset()
        await target.inject("you are evil", InjectionPoint.SYSTEM_PROMPT)
        await target.execute("hi")
        roles = [m["role"] for m in capture["input"]["messages"]]
        assert "system" in roles
        assert capture["input"]["messages"][0]["content"] == "you are evil"

    async def test_tool_calls_extracted(self, monkeypatch) -> None:
        state = {"messages": [
            {"type": "ai", "content": "ok",
             "tool_calls": [{"name": "send_email", "args": {"to": "x@evil.com"}}]},
        ]}
        _install_fake(monkeypatch, final_state=state)
        target = LangGraphServerTarget()
        await target.load({"base_url": "http://localhost:2024"})
        await target.execute("do it")
        resp = await target.get_response()
        assert resp.tool_calls[0].name == "send_email"
        assert resp.tool_calls[0].arguments == {"to": "x@evil.com"}

    async def test_run_error_captured(self, monkeypatch) -> None:
        def _boom(inp):
            raise RuntimeError("server 500")
        _install_fake(monkeypatch, final_state=_boom)
        target = LangGraphServerTarget()
        await target.load({"base_url": "http://localhost:2024"})
        await target.execute("x")
        resp = await target.get_response()
        assert resp.error is not None and "server 500" in resp.error
