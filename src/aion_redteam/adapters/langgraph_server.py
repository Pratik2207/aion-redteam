"""LangGraph Server (HTTP) target adapter.

Red-teams a LangGraph agent that runs as a **server** — e.g. ``langgraph dev`` on
``http://127.0.0.1:2024`` or a deployed LangGraph Platform graph — instead of an
importable in-process graph. This means aion-redteam does not need to be installed in
the agent's environment; it talks to the running service over HTTP via ``langgraph_sdk``.

The adapter discovers the available graphs/assistants on the server, opens a fresh thread
per run, submits the (possibly injected) message list, and reads the final state back.
"""

from __future__ import annotations

import time
from typing import Any

from aion_redteam.adapters._injection import fold_injection
from aion_redteam.core.scenario import InjectionPoint, Setup
from aion_redteam.core.target import Target, TargetError, TargetResponse, ToolCall

DEFAULT_BASE_URL = "http://127.0.0.1:2024"
DEFAULT_ASSISTANT = "agent"


class LangGraphServerTarget(Target):
    """A :class:`Target` backed by a running LangGraph Server."""

    def __init__(self) -> None:
        """Create an unloaded adapter; call :meth:`load` before running."""
        self._client: Any | None = None
        self._assistant_id: str = DEFAULT_ASSISTANT
        self._messages_key = "messages"
        self._system_prompt: str | None = None
        self._injection: tuple[str, InjectionPoint] | None = None
        self._last_response: TargetResponse | None = None

    async def load(self, config: dict[str, Any]) -> None:
        """Connect to the server and resolve the assistant/graph to test.

        Args:
            config: May contain ``base_url`` (default ``http://127.0.0.1:2024``),
                ``assistant`` (graph/assistant id or name, default ``"agent"``),
                ``api_key`` (for hosted/authenticated servers), and ``messages_key``.

        Raises:
            TargetError: If ``langgraph_sdk`` is missing, the server is unreachable,
                or the requested assistant cannot be found.
        """
        try:
            from langgraph_sdk import get_client
        except ImportError as exc:
            raise TargetError(
                "langgraph-server adapter requires langgraph-sdk. "
                'Install with: pip install "aion-redteam[langgraph-server]"'
            ) from exc

        base_url = config.get("base_url") or DEFAULT_BASE_URL
        requested = config.get("assistant") or DEFAULT_ASSISTANT
        self._messages_key = config.get("messages_key", "messages")
        api_key = config.get("api_key")

        self._client = get_client(url=base_url, api_key=api_key)
        self._assistant_id = await self._resolve_assistant(base_url, requested)

    async def _resolve_assistant(self, base_url: str, requested: str) -> str:
        """Find the assistant whose graph_id/assistant_id/name matches ``requested``."""
        try:
            assistants = await self._client.assistants.search(limit=100)
        except Exception as exc:  # noqa: BLE001 - connection/HTTP problems become TargetError
            raise TargetError(
                f"could not reach LangGraph server at {base_url}: {exc}. "
                "Is the server running (e.g. `langgraph dev`)?"
            ) from exc

        available: list[str] = []
        for a in assistants:
            graph_id = a.get("graph_id", "")
            assistant_id = a.get("assistant_id", "")
            name = a.get("name", "")
            available.append(graph_id or name or assistant_id)
            if requested in (graph_id, assistant_id, name):
                # Prefer the canonical assistant_id for run submission.
                return assistant_id or graph_id or requested

        raise TargetError(
            f"assistant {requested!r} not found on {base_url}. "
            f"Available graphs: {', '.join(sorted(set(available))) or '(none)'}. "
            "Pass --assistant with one of these."
        )

    async def configure(self, setup: Setup) -> None:
        """Record the scenario's legitimate system prompt, if any."""
        self._system_prompt = setup.system_prompt

    async def inject(self, payload: str, injection_point: InjectionPoint) -> None:
        """Stage the attack payload for the next execution."""
        self._injection = (payload, injection_point)

    async def execute(self, input_message: str) -> None:
        """Open a thread, submit the (injected) messages, and wait for the result."""
        if self._client is None:
            raise TargetError("server client not loaded; call load() first")

        system_text, user_text = fold_injection(
            input_message, self._injection, self._system_prompt
        )
        messages: list[dict[str, str]] = []
        if system_text:
            messages.append({"role": "system", "content": system_text})
        messages.append({"role": "user", "content": user_text})

        started = time.perf_counter()
        try:
            thread = await self._client.threads.create()
            state = await self._client.runs.wait(
                thread["thread_id"],
                self._assistant_id,
                input={self._messages_key: messages},
            )
        except Exception as exc:  # noqa: BLE001 - surfaced as a captured run error
            self._last_response = TargetResponse(
                error=f"{type(exc).__name__}: {exc}",
                duration_ms=int((time.perf_counter() - started) * 1000),
            )
            return
        duration_ms = int((time.perf_counter() - started) * 1000)
        self._last_response = self._extract_response(state, duration_ms)

    async def get_response(self) -> TargetResponse:
        """Return the response captured by the most recent :meth:`execute`."""
        if self._last_response is None:
            raise TargetError("no response captured; call execute() first")
        return self._last_response

    async def reset(self) -> None:
        """Clear per-run state (a fresh thread is created per execute)."""
        self._injection = None
        self._system_prompt = None
        self._last_response = None

    # -- internals -----------------------------------------------------------------

    def _extract_response(self, state: Any, duration_ms: int) -> TargetResponse:
        """Pull final output, tool calls, and trace out of the server's run result."""
        messages = []
        if isinstance(state, dict):
            messages = state.get(self._messages_key, []) or []

        final_output = ""
        tool_calls: list[ToolCall] = []
        trace: list[str] = []
        for msg in messages:
            mtype = _msg_type(msg)
            text = _content_text(_msg_field(msg, "content"))
            trace.append(f"{mtype}: {text}")
            for call in _msg_field(msg, "tool_calls") or []:
                tool_calls.append(
                    ToolCall(
                        name=_msg_field(call, "name") or "",
                        arguments=_msg_field(call, "args")
                        or _msg_field(call, "arguments")
                        or {},
                    )
                )
            if mtype in ("ai", "assistant") and text:
                final_output = text

        return TargetResponse(
            final_output=final_output,
            tool_calls=tool_calls,
            full_trace=trace,
            duration_ms=duration_ms,
        )


def _msg_field(obj: Any, field: str) -> Any:
    """Read a field from a message that may be a dict or an object."""
    if isinstance(obj, dict):
        return obj.get(field)
    return getattr(obj, field, None)


def _msg_type(msg: Any) -> str:
    """Return a message's role/type (``human``/``ai``/``tool``/...)."""
    return str(_msg_field(msg, "type") or _msg_field(msg, "role") or "message")


def _content_text(content: Any) -> str:
    """Normalize message content (string or list of content blocks) to text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                parts.append(str(block.get("text", "")))
            else:
                parts.append(str(block))
        return "".join(parts)
    return "" if content is None else str(content)
