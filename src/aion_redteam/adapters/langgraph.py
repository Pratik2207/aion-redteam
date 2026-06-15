"""LangGraph target adapter.

Wraps a user's *real* compiled LangGraph graph and drives it through the harness
lifecycle. The adapter is LLM-agnostic — it only invokes the compiled graph; whichever
model the graph uses is the model that gets red-teamed.

The graph is expected to use a ``messages`` state key (the LangGraph ``MessagesState``
convention). The adapter delivers each injection point by shaping the message list it
feeds the graph; see ``docs/adapter_guide.md`` for the per-channel encoding and its
limitations on single-node agents.
"""

from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path
from typing import Any

from aion_redteam.adapters._injection import fold_injection
from aion_redteam.core.scenario import InjectionPoint, Setup
from aion_redteam.core.target import Target, TargetError, TargetResponse, ToolCall

# Attribute names searched (in order) for an already-compiled graph.
_GRAPH_CANDIDATES = ("graph", "app", "agent", "workflow")
# Factory function names searched (in order); each is called with no arguments.
_FACTORY_CANDIDATES = ("build_graph", "make_graph", "get_graph", "build_agent")


class LangGraphTarget(Target):
    """A :class:`Target` backed by a compiled LangGraph graph."""

    def __init__(self) -> None:
        """Create an unloaded adapter; call :meth:`load` before running."""
        self._graph: Any | None = None
        self._messages_key = "messages"
        self._system_prompt: str | None = None
        self._injection: tuple[str, InjectionPoint] | None = None
        self._last_response: TargetResponse | None = None

    async def load(self, config: dict[str, Any]) -> None:
        """Import the user's module and locate its compiled graph.

        Args:
            config: Must contain ``target`` (path to a ``.py`` file). May contain
                ``attribute`` (explicit name of the compiled graph) and
                ``messages_key`` (state key holding the message list; default
                ``"messages"``).

        Raises:
            TargetError: If the file or a compiled graph cannot be found.
        """
        target = config.get("target")
        if not target:
            raise TargetError("langgraph adapter requires a 'target' file path")
        self._messages_key = config.get("messages_key", "messages")
        module = self._import_module(Path(target))
        self._graph = self._locate_graph(module, config.get("attribute"))

    async def configure(self, setup: Setup) -> None:
        """Record the scenario's legitimate system prompt, if any."""
        self._system_prompt = setup.system_prompt

    async def inject(self, payload: str, injection_point: InjectionPoint) -> None:
        """Stage the attack payload for the next execution."""
        self._injection = (payload, injection_point)

    async def execute(self, input_message: str) -> None:
        """Build the message list (applying any injection) and invoke the graph."""
        if self._graph is None:
            raise TargetError("graph not loaded; call load() first")

        messages = self._build_messages(input_message)
        started = time.perf_counter()
        try:
            state = await self._graph.ainvoke({self._messages_key: messages})
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
        """Clear per-run state (staged injection, system prompt, last response)."""
        self._injection = None
        self._system_prompt = None
        self._last_response = None

    # -- internals -----------------------------------------------------------------

    def _build_messages(self, input_message: str) -> list[Any]:
        """Construct the langchain message list, folding in the staged injection."""
        from langchain_core.messages import HumanMessage, SystemMessage

        system_text, user_text = fold_injection(
            input_message, self._injection, self._system_prompt
        )
        messages: list[Any] = []
        if system_text:
            messages.append(SystemMessage(content=system_text))
        messages.append(HumanMessage(content=user_text))
        return messages

    def _extract_response(self, state: Any, duration_ms: int) -> TargetResponse:
        """Pull the final output, tool calls, and trace out of the graph's end state."""
        messages = self._state_messages(state)
        final_output = ""
        tool_calls: list[ToolCall] = []
        trace: list[str] = []

        for msg in messages:
            text = _message_text(msg)
            trace.append(f"{type(msg).__name__}: {text}")
            for call in getattr(msg, "tool_calls", None) or []:
                tool_calls.append(
                    ToolCall(
                        name=_tool_call_field(call, "name"),
                        arguments=_tool_call_field(call, "args") or {},
                    )
                )
            if type(msg).__name__ == "AIMessage" and text:
                final_output = text

        return TargetResponse(
            final_output=final_output,
            tool_calls=tool_calls,
            full_trace=trace,
            duration_ms=duration_ms,
        )

    def _state_messages(self, state: Any) -> list[Any]:
        """Return the message list from the graph's output state."""
        if isinstance(state, dict):
            return state.get(self._messages_key, []) or []
        return getattr(state, self._messages_key, []) or []

    @staticmethod
    def _import_module(path: Path) -> Any:
        """Import a Python module from a file path, making sibling imports resolvable.

        Security note: this executes the target file's module-level code (loading an
        agent requires running it). Only point aion-redteam at agent files you trust.
        The target's directory is *appended* to ``sys.path`` (not prepended) so it cannot
        shadow stdlib or installed packages.
        """
        path = path.resolve()
        if not path.is_file():
            raise TargetError(f"target file not found: {path}")
        parent = str(path.parent)
        if parent not in sys.path:
            sys.path.append(parent)
        module_name = f"_aion_target_{path.stem}"
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise TargetError(f"could not import target module: {path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
        except Exception as exc:  # noqa: BLE001 - report import-time failures clearly
            raise TargetError(f"error importing {path}: {exc}") from exc
        return module

    @staticmethod
    def _locate_graph(module: Any, attribute: str | None) -> Any:
        """Find the compiled graph in ``module`` by attribute, candidate, or factory."""
        if attribute is not None:
            if not hasattr(module, attribute):
                raise TargetError(f"module has no attribute {attribute!r}")
            return _as_compiled_graph(getattr(module, attribute), attribute)

        for name in _GRAPH_CANDIDATES:
            obj = getattr(module, name, None)
            if _looks_compiled(obj):
                return obj

        for name in _FACTORY_CANDIDATES:
            factory = getattr(module, name, None)
            if callable(factory):
                built = factory()
                if _looks_compiled(built):
                    return built

        raise TargetError(
            "no compiled LangGraph graph found. Expose one as a module-level "
            f"variable named one of {_GRAPH_CANDIDATES}, a factory in "
            f"{_FACTORY_CANDIDATES}, or pass an explicit 'attribute'."
        )


def _looks_compiled(obj: Any) -> bool:
    """Heuristic: a compiled graph is invocable via ``ainvoke``/``invoke``."""
    return obj is not None and hasattr(obj, "ainvoke") and hasattr(obj, "invoke")


def _as_compiled_graph(obj: Any, name: str) -> Any:
    """Validate that an explicitly named attribute is a compiled graph."""
    if not _looks_compiled(obj):
        raise TargetError(f"attribute {name!r} is not a compiled LangGraph graph")
    return obj


def _message_text(msg: Any) -> str:
    """Normalize a langchain message's content (str or content blocks) to text."""
    content = getattr(msg, "content", msg)
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
    return str(content)


def _tool_call_field(call: Any, field: str) -> Any:
    """Read a field from a tool-call record that may be a dict or an object."""
    if isinstance(call, dict):
        return call.get(field)
    return getattr(call, field, None)
