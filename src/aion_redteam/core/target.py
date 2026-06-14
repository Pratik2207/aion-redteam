"""The :class:`Target` abstraction — one adapter per agent framework implements it.

A target wraps a user's real agent. The runner drives it through a fixed lifecycle:
``reset -> inject -> execute -> get_response``. Adapters translate that lifecycle into
framework-specific calls (LangGraph graph invocation, CrewAI crew kickoff, an MCP
session, …). Targets always exercise the *real* agent; mocking belongs in unit tests
of individual components, never on this path.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from aion_redteam.core.scenario import InjectionPoint, Setup


class ToolCall(BaseModel):
    """A single tool/function invocation made by the agent during a run."""

    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    output: str | None = None


class TargetResponse(BaseModel):
    """Everything the harness captures from one agent execution."""

    final_output: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    full_trace: list[str] = Field(default_factory=list)
    error: str | None = None
    duration_ms: int = 0

    def render_tool_calls(self) -> str:
        """Flatten tool calls into a searchable string for judges.

        Returns:
            One line per tool call (``name(arguments) -> output``), suitable for
            judges whose criterion target is ``tool_calls``.
        """
        lines: list[str] = []
        for call in self.tool_calls:
            line = f"{call.name}({call.arguments})"
            if call.output is not None:
                line += f" -> {call.output}"
            lines.append(line)
        return "\n".join(lines)

    def render_full_trace(self) -> str:
        """Join the full execution trace into a single searchable string."""
        return "\n".join(self.full_trace)

    def tool_calls_as_json(self) -> str:
        """Serialize tool calls to JSON for structured checking by ToolCallJudge.

        Returns:
            A JSON array of ``{"name": ..., "arguments": {...}}`` objects.
        """
        return json.dumps(
            [{"name": c.name, "arguments": c.arguments} for c in self.tool_calls]
        )


class TargetError(Exception):
    """Raised by adapters for load/configuration failures (not agent-runtime errors).

    Agent-runtime errors should be captured in ``TargetResponse.error`` so the runner
    can classify the scenario as ``ERROR`` rather than aborting the whole run.
    """


class Target(ABC):
    """Abstract base class for an agent target under test.

    Lifecycle, driven by the runner once per repetition:

    1. :meth:`reset` — restore clean state.
    2. :meth:`configure` — apply the scenario's legitimate setup (system prompt, tools).
    3. :meth:`inject` — stage the attack payload at its injection point.
    4. :meth:`execute` — run the agent on the legitimate input.
    5. :meth:`get_response` — return what the agent did.
    """

    async def configure(self, setup: Setup) -> None:
        """Apply the scenario's legitimate setup before any attack is staged.

        Adapters may use ``setup.system_prompt`` and ``setup.tools_available`` to
        shape the agent's environment. The default is a no-op so adapters that do
        not support reconfiguration still satisfy the interface.

        Args:
            setup: The scenario's legitimate (pre-attack) configuration.
        """
        return None

    @abstractmethod
    async def load(self, config: dict[str, Any]) -> None:
        """Load the user's agent from a file/module path and prepare it for runs.

        Args:
            config: Adapter-specific configuration (e.g. ``{"target": "agent.py"}``).

        Raises:
            TargetError: If the agent cannot be located or loaded.
        """

    @abstractmethod
    async def inject(self, payload: str, injection_point: InjectionPoint) -> None:
        """Stage an attack payload to be delivered at ``injection_point``.

        Args:
            payload: The adversarial content.
            injection_point: Where the payload should enter the agent's data flow.
        """

    @abstractmethod
    async def execute(self, input_message: str) -> None:
        """Run the agent on the legitimate input, applying any staged injection.

        Args:
            input_message: The benign task the agent is ostensibly asked to perform.
        """

    @abstractmethod
    async def get_response(self) -> TargetResponse:
        """Return the captured response from the most recent :meth:`execute`."""

    @abstractmethod
    async def reset(self) -> None:
        """Clear staged injections and per-run state before the next repetition."""
