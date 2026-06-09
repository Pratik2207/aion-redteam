"""Unit tests for the scenario schema and loader."""

from __future__ import annotations

import textwrap

import pytest

from aion_redteam.core.scenario import (
    CombineMode,
    InjectionPoint,
    OwaspCategory,
    Scenario,
    ScenarioLoader,
    ScenarioLoadError,
    Severity,
)


class TestValidLoading:
    def test_loads_valid_scenario(self, valid_scenario_path) -> None:
        scenario = ScenarioLoader(valid_scenario_path).load_file(valid_scenario_path)
        assert scenario.id == "ASI01-001"
        assert scenario.owasp_category is OwaspCategory.ASI01
        assert scenario.severity is Severity.HIGH
        assert scenario.attack.injection_point is InjectionPoint.USER_MESSAGE
        assert scenario.success_criteria.mode is CombineMode.ANY
        assert len(scenario.success_criteria.criteria) == 2

    def test_defaults_applied(self, valid_scenario_path) -> None:
        scenario = ScenarioLoader(valid_scenario_path).load_file(valid_scenario_path)
        # execution provided in fixture, but verify a defaulted field on a criterion
        assert scenario.success_criteria.criteria[0].case_sensitive is False

    def test_discover_recurses(self, tmp_path, valid_scenario_path) -> None:
        nested = tmp_path / "ASI02" / "deep.yaml"
        nested.parent.mkdir(parents=True)
        nested.write_text(valid_scenario_path.read_text(encoding="utf-8"), encoding="utf-8")
        found = ScenarioLoader(tmp_path).discover()
        assert nested in found

    def test_load_all_sorted_by_id(self, tmp_path, write_scenario) -> None:
        from tests.conftest import VALID_SCENARIO_YAML

        write_scenario(VALID_SCENARIO_YAML, "a.yaml")
        second = VALID_SCENARIO_YAML.replace("ASI01-001", "ASI01-009")
        write_scenario(second, "b.yaml")
        scenarios = ScenarioLoader(tmp_path).load_all()
        assert [s.id for s in scenarios] == ["ASI01-001", "ASI01-009"]


class TestValidationErrors:
    def test_malformed_yaml(self, write_scenario) -> None:
        path = write_scenario("id: [unclosed\n")
        with pytest.raises(ScenarioLoadError, match="invalid YAML"):
            ScenarioLoader(path).load_file(path)

    def test_non_mapping_yaml(self, write_scenario) -> None:
        path = write_scenario("- just\n- a\n- list\n")
        with pytest.raises(ScenarioLoadError, match="must contain a YAML mapping"):
            ScenarioLoader(path).load_file(path)

    def test_missing_required_field(self, write_scenario) -> None:
        path = write_scenario("id: ASI01-001\nowasp_category: ASI01\n")
        with pytest.raises(ScenarioLoadError):
            ScenarioLoader(path).load_file(path)

    def test_extra_field_forbidden(self, write_scenario) -> None:
        content = textwrap.dedent(
            """
            id: "ASI01-001"
            name: "x"
            owasp_category: "ASI01"
            severity: "low"
            setup:
              agent_input: "hi"
            attack:
              injection_point: "user_message"
              payload: "x"
            success_criteria:
              criteria:
                - type: "string_match"
                  value: "x"
            bogus_field: true
            """
        ).strip()
        path = write_scenario(content)
        with pytest.raises(ScenarioLoadError, match="bogus_field"):
            ScenarioLoader(path).load_file(path)

    def test_id_prefix_must_match_category(self, write_scenario) -> None:
        content = textwrap.dedent(
            """
            id: "ASI09-001"
            name: "x"
            owasp_category: "ASI01"
            severity: "low"
            setup:
              agent_input: "hi"
            attack:
              injection_point: "user_message"
              payload: "x"
            success_criteria:
              criteria:
                - type: "string_match"
                  value: "x"
            """
        ).strip()
        path = write_scenario(content)
        with pytest.raises(ScenarioLoadError, match="must start with"):
            ScenarioLoader(path).load_file(path)


class TestCriterionValidation:
    def test_regex_requires_pattern(self) -> None:
        with pytest.raises(ValueError, match="requires 'pattern'"):
            Scenario.model_validate(
                {
                    "id": "ASI01-001",
                    "name": "x",
                    "owasp_category": "ASI01",
                    "severity": "low",
                    "setup": {"agent_input": "hi"},
                    "attack": {"injection_point": "user_message", "payload": "x"},
                    "success_criteria": {"criteria": [{"type": "regex"}]},
                }
            )

    def test_multi_turn_requires_turns(self) -> None:
        with pytest.raises(ValueError, match="requires a non-empty 'turns'"):
            Scenario.model_validate(
                {
                    "id": "ASI01-001",
                    "name": "x",
                    "owasp_category": "ASI01",
                    "severity": "low",
                    "setup": {"agent_input": "hi"},
                    "attack": {
                        "injection_point": "user_message",
                        "payload": "x",
                        "multi_turn": True,
                    },
                    "success_criteria": {"criteria": [{"type": "string_match", "value": "x"}]},
                }
            )
