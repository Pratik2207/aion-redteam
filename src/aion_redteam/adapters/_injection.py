"""Shared helper for folding an attack payload into an agent's messages.

Both the in-process LangGraph adapter and the LangGraph Server (HTTP) adapter deliver
each injection point the same way; only the final message *representation* differs
(langchain message objects vs. JSON message dicts). This module owns the channel logic.
"""

from __future__ import annotations

from aion_redteam.core.scenario import InjectionPoint

# How each injection point is labelled when woven into the user message.
CHANNEL_LABELS: dict[InjectionPoint, str] = {
    InjectionPoint.TOOL_OUTPUT: "Tool output",
    InjectionPoint.RAG_DOCUMENT: "Retrieved document",
    InjectionPoint.MEMORY: "Recalled memory",
    InjectionPoint.INTER_AGENT_MESSAGE: "Message from peer agent",
}


def fold_injection(
    input_message: str,
    injection: tuple[str, InjectionPoint] | None,
    system_prompt: str | None,
) -> tuple[str | None, str]:
    """Combine the benign task and the staged attack into (system_text, user_text).

    Args:
        input_message: The legitimate user task.
        injection: ``(payload, injection_point)`` staged by ``inject()``, or ``None``.
        system_prompt: The scenario's legitimate system prompt, if any.

    Returns:
        ``(system_text, user_text)`` where ``system_text`` may be ``None``.
    """
    system_text = system_prompt
    user_text = input_message

    if injection is not None:
        payload, point = injection
        if point == InjectionPoint.SYSTEM_PROMPT:
            system_text = payload
        elif point == InjectionPoint.USER_MESSAGE:
            user_text = f"{input_message}\n\n{payload}"
        else:
            label = CHANNEL_LABELS.get(point, "Context")
            user_text = f"{input_message}\n\n[{label}]:\n{payload}"

    return system_text, user_text
