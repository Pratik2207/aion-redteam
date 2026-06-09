"""Unit tests for the Phase 1 judges."""

from __future__ import annotations

import pytest

from aion_redteam.core.judge import (
    LLMJudge,
    RegexJudge,
    StringMatchJudge,
    ToolCallJudge,
    get_judge,
)
from aion_redteam.core.scenario import Criterion, CriterionType


class TestStringMatchJudge:
    def test_substring_match_case_insensitive_by_default(self) -> None:
        judge = StringMatchJudge()
        crit = Criterion(type=CriterionType.STRING_MATCH, value="attacker@evil.com")
        assert judge.evaluate("Email ATTACKER@EVIL.COM now", crit) is True

    def test_no_match(self) -> None:
        judge = StringMatchJudge()
        crit = Criterion(type=CriterionType.STRING_MATCH, value="attacker@evil.com")
        assert judge.evaluate("a benign response", crit) is False

    def test_case_sensitive_respected(self) -> None:
        judge = StringMatchJudge()
        crit = Criterion(
            type=CriterionType.STRING_MATCH, value="EvilBot", case_sensitive=True
        )
        assert judge.evaluate("i am evilbot", crit) is False
        assert judge.evaluate("i am EvilBot", crit) is True


class TestRegexJudge:
    def test_pattern_search(self) -> None:
        judge = RegexJudge()
        crit = Criterion(type=CriterionType.REGEX, pattern="smtplib|sendmail")
        assert judge.evaluate("import smtplib", crit) is True

    def test_ignorecase_flag(self) -> None:
        judge = RegexJudge()
        crit = Criterion(
            type=CriterionType.REGEX, pattern="EVIL", flags=["IGNORECASE"]
        )
        assert judge.evaluate("be evil", crit) is True

    def test_case_sensitive_disables_default_ignorecase(self) -> None:
        judge = RegexJudge()
        crit = Criterion(type=CriterionType.REGEX, pattern="EVIL", case_sensitive=True)
        assert judge.evaluate("be evil", crit) is False

    def test_unknown_flag_raises(self) -> None:
        judge = RegexJudge()
        crit = Criterion(type=CriterionType.REGEX, pattern="x", flags=["NONSENSE"])
        with pytest.raises(ValueError, match="unknown regex flag"):
            judge.evaluate("x", crit)


class TestStubs:
    def test_llm_judge_not_implemented(self) -> None:
        crit = Criterion(type=CriterionType.LLM_JUDGE, prompt="did it leak?")
        with pytest.raises(NotImplementedError, match="v0.2"):
            LLMJudge().evaluate("anything", crit)

    def test_tool_call_judge_not_implemented(self) -> None:
        crit = Criterion(type=CriterionType.TOOL_CALL_CHECK, value="send_email")
        with pytest.raises(NotImplementedError):
            ToolCallJudge().evaluate("anything", crit)


class TestGetJudge:
    @pytest.mark.parametrize(
        ("ctype", "expected"),
        [
            (CriterionType.STRING_MATCH, StringMatchJudge),
            (CriterionType.REGEX, RegexJudge),
            (CriterionType.LLM_JUDGE, LLMJudge),
            (CriterionType.TOOL_CALL_CHECK, ToolCallJudge),
        ],
    )
    def test_factory_returns_correct_judge(self, ctype, expected) -> None:
        assert isinstance(get_judge(ctype), expected)
