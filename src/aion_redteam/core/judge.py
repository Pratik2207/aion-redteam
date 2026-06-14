"""Judges: pluggable evaluators that decide whether a single criterion matched.

A judge answers one question: *given this slice of the agent's behaviour, did this
criterion match?* The runner picks the slice (response text, tool calls, or trace)
based on ``criterion.target`` and hands the judge a plain string.

Phase 1 ships :class:`StringMatchJudge` and :class:`RegexJudge`. :class:`LLMJudge` and
:class:`ToolCallJudge` are stubs that raise until their respective phases land.
"""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from typing import Any

from aion_redteam.core.scenario import Criterion, CriterionType

# Named regex flags accepted in scenario YAML (``flags: ["IGNORECASE", ...]``).
_REGEX_FLAGS: dict[str, re.RegexFlag] = {
    "IGNORECASE": re.IGNORECASE,
    "MULTILINE": re.MULTILINE,
    "DOTALL": re.DOTALL,
    "VERBOSE": re.VERBOSE,
    "ASCII": re.ASCII,
}


class Judge(ABC):
    """Abstract base class for all judges."""

    @abstractmethod
    def evaluate(self, response: str, criterion: Criterion) -> bool:
        """Return ``True`` if ``criterion`` matches ``response``.

        Args:
            response: The agent-behaviour slice selected by ``criterion.target``.
            criterion: The criterion to evaluate.

        Returns:
            ``True`` when the criterion matches (i.e. the attack indicator is present).
        """
        raise NotImplementedError


class StringMatchJudge(Judge):
    """Substring match. Case-insensitive unless ``criterion.case_sensitive`` is set."""

    def evaluate(self, response: str, criterion: Criterion) -> bool:
        """Check whether ``criterion.value`` is a substring of ``response``."""
        if criterion.value is None:
            raise ValueError("string_match criterion requires 'value'")
        if criterion.case_sensitive:
            return criterion.value in response
        return criterion.value.casefold() in response.casefold()


class RegexJudge(Judge):
    """Regex search using ``criterion.pattern`` with optional named ``flags``."""

    def evaluate(self, response: str, criterion: Criterion) -> bool:
        """Search ``response`` for ``criterion.pattern``."""
        if criterion.pattern is None:
            raise ValueError("regex criterion requires 'pattern'")
        flags = self._resolve_flags(criterion)
        return re.search(criterion.pattern, response, flags) is not None

    @staticmethod
    def _resolve_flags(criterion: Criterion) -> int:
        """Combine named regex flags from the criterion into a single bitmask."""
        bitmask = 0
        for name in criterion.flags:
            try:
                bitmask |= _REGEX_FLAGS[name.upper()]
            except KeyError as exc:
                valid = ", ".join(sorted(_REGEX_FLAGS))
                raise ValueError(
                    f"unknown regex flag {name!r}; valid flags: {valid}"
                ) from exc
        if not criterion.case_sensitive and not (bitmask & re.IGNORECASE):
            bitmask |= re.IGNORECASE
        return bitmask


class LLMJudge(Judge):
    """Scores agent output with an LLM. Available in v0.2."""

    def evaluate(self, response: str, criterion: Criterion) -> bool:
        """Not implemented until v0.2."""
        raise NotImplementedError(
            "LLMJudge available in v0.2. Install aion-redteam[llm-judge]"
        )


class ToolCallJudge(Judge):
    """Checks whether the agent invoked a specific tool, optionally with given arguments.

    The runner feeds this judge a JSON array of the agent's tool calls
    (``[{"name": ..., "arguments": {...}}, ...]`` from
    :meth:`TargetResponse.tool_calls_as_json`). The criterion's ``value`` is the tool
    name to look for; the optional ``arguments`` mapping requires each named argument's
    value to contain the given substring.
    """

    def evaluate(self, response: str, criterion: Criterion) -> bool:
        """Return ``True`` if a matching tool call is present."""
        if criterion.value is None:
            raise ValueError("tool_call_check criterion requires 'value' (the tool name)")
        try:
            calls = json.loads(response) if response else []
        except json.JSONDecodeError:
            return False
        if not isinstance(calls, list):
            return False
        return any(self._matches(call, criterion) for call in calls)

    def _matches(self, call: Any, criterion: Criterion) -> bool:
        """Check one tool-call record against the criterion."""
        if not isinstance(call, dict):
            return False
        if not self._name_matches(str(call.get("name", "")), criterion):
            return False
        if not criterion.arguments:
            return True
        args = call.get("arguments") or {}
        if not isinstance(args, dict):
            return False
        return all(
            expected in str(args.get(key, "")) for key, expected in criterion.arguments.items()
        )

    @staticmethod
    def _name_matches(name: str, criterion: Criterion) -> bool:
        """Compare a tool name to the criterion's target name, honouring case mode."""
        target = criterion.value or ""
        if criterion.case_sensitive:
            return name == target
        return name.casefold() == target.casefold()


_JUDGE_REGISTRY: dict[CriterionType, type[Judge]] = {
    CriterionType.STRING_MATCH: StringMatchJudge,
    CriterionType.REGEX: RegexJudge,
    CriterionType.LLM_JUDGE: LLMJudge,
    CriterionType.TOOL_CALL_CHECK: ToolCallJudge,
}


def get_judge(criterion_type: CriterionType) -> Judge:
    """Return a judge instance for the given criterion type.

    Args:
        criterion_type: The criterion type to evaluate.

    Returns:
        A ready-to-use :class:`Judge`.

    Raises:
        KeyError: If no judge is registered for ``criterion_type``.
    """
    return _JUDGE_REGISTRY[criterion_type]()
