"""Pydantic models and loader for the adversarial scenario YAML schema.

A *scenario* is a single, self-contained adversarial test: a legitimate setup, an
attack payload injected at a defined point, and unambiguous success criteria. Scenarios
are **data, not code** — every attack ships as a YAML file validated against these models.

The schema here is the contract documented in ``docs/scenario_authoring.md``.
"""

from __future__ import annotations

import enum
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


class OwaspCategory(enum.StrEnum):
    """The OWASP Agentic Top 10 (ASI) categories for 2026."""

    ASI01 = "ASI01"  # Agent Goal Hijack
    ASI02 = "ASI02"  # Tool Misuse & Exploitation
    ASI03 = "ASI03"  # Agent Identity & Privilege Abuse
    ASI04 = "ASI04"  # Agentic Supply Chain Compromise
    ASI05 = "ASI05"  # Unexpected Code Execution
    ASI06 = "ASI06"  # Memory & Context Poisoning
    ASI07 = "ASI07"  # Insecure Inter-Agent Communication
    ASI08 = "ASI08"  # Cascading Agent Failures
    ASI09 = "ASI09"  # Human-Agent Trust Exploitation
    ASI10 = "ASI10"  # Rogue Agents


# Human-readable names, kept next to the enum so reports and the CLI stay in sync.
OWASP_CATEGORY_NAMES: dict[OwaspCategory, str] = {
    OwaspCategory.ASI01: "Agent Goal Hijack",
    OwaspCategory.ASI02: "Tool Misuse & Exploitation",
    OwaspCategory.ASI03: "Agent Identity & Privilege Abuse",
    OwaspCategory.ASI04: "Agentic Supply Chain Compromise",
    OwaspCategory.ASI05: "Unexpected Code Execution",
    OwaspCategory.ASI06: "Memory & Context Poisoning",
    OwaspCategory.ASI07: "Insecure Inter-Agent Communication",
    OwaspCategory.ASI08: "Cascading Agent Failures",
    OwaspCategory.ASI09: "Human-Agent Trust Exploitation",
    OwaspCategory.ASI10: "Rogue Agents",
}


class Severity(enum.StrEnum):
    """Real-world impact of a successful attack."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Difficulty(enum.StrEnum):
    """Sophistication of the attack payload."""

    BASIC = "basic"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class InjectionPoint(enum.StrEnum):
    """Where in the agent's data flow the attack payload is delivered."""

    USER_MESSAGE = "user_message"
    TOOL_OUTPUT = "tool_output"
    RAG_DOCUMENT = "rag_document"
    MEMORY = "memory"
    SYSTEM_PROMPT = "system_prompt"
    INTER_AGENT_MESSAGE = "inter_agent_message"


class CriterionType(enum.StrEnum):
    """The kind of check a success criterion performs."""

    STRING_MATCH = "string_match"
    REGEX = "regex"
    LLM_JUDGE = "llm_judge"
    TOOL_CALL_CHECK = "tool_call_check"


class CriterionTarget(enum.StrEnum):
    """Which part of the agent's behaviour a criterion is evaluated against."""

    AGENT_RESPONSE = "agent_response"
    TOOL_CALLS = "tool_calls"
    FULL_TRACE = "full_trace"


class CombineMode(enum.StrEnum):
    """How multiple criteria combine into a single attack-success decision."""

    ANY = "any"
    ALL = "all"


class StrictModel(BaseModel):
    """Base model that forbids unknown fields so malformed YAML fails loudly."""

    model_config = ConfigDict(extra="forbid", use_enum_values=False)


class Criterion(StrictModel):
    """A single success check.

    The relevant fields depend on ``type``:

    * ``string_match`` requires ``value`` (and may set ``case_sensitive``).
    * ``regex`` requires ``pattern`` (and may set ``flags``).
    * ``llm_judge`` uses ``prompt`` (handled in v0.2).
    * ``tool_call_check`` uses ``value``/``arguments`` (handled in a later phase).
    """

    type: CriterionType
    target: CriterionTarget = CriterionTarget.AGENT_RESPONSE

    # string_match / tool_call_check
    value: str | None = None
    case_sensitive: bool = False

    # regex
    pattern: str | None = None
    flags: list[str] = Field(default_factory=list)

    # llm_judge
    prompt: str | None = None

    # tool_call_check
    arguments: dict[str, str] | None = None

    @model_validator(mode="after")
    def _check_required_for_type(self) -> Criterion:
        """Ensure the fields required by this criterion's type are present."""
        if self.type == CriterionType.STRING_MATCH and self.value is None:
            raise ValueError("string_match criterion requires 'value'")
        if self.type == CriterionType.REGEX and self.pattern is None:
            raise ValueError("regex criterion requires 'pattern'")
        if self.type == CriterionType.TOOL_CALL_CHECK and self.value is None:
            raise ValueError("tool_call_check criterion requires 'value' (the tool name)")
        return self


class SuccessCriteria(StrictModel):
    """A set of criteria plus the rule for combining them."""

    mode: CombineMode = CombineMode.ANY
    criteria: list[Criterion] = Field(min_length=1)


class Turn(StrictModel):
    """One message in a multi-turn attack."""

    role: str
    content: str


class Attack(StrictModel):
    """The adversarial payload and how it is delivered."""

    injection_point: InjectionPoint
    payload: str
    multi_turn: bool = False
    turns: list[Turn] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_turns(self) -> Attack:
        """Multi-turn attacks must supply their turn sequence."""
        if self.multi_turn and not self.turns:
            raise ValueError("multi_turn attack requires a non-empty 'turns' list")
        return self


class ToolSpec(StrictModel):
    """Declaration of a tool the agent has access to during the scenario."""

    name: str
    description: str = ""


class Setup(StrictModel):
    """The legitimate task the agent receives, before any attack."""

    agent_input: str
    system_prompt: str | None = None
    tools_available: list[ToolSpec] = Field(default_factory=list)


class Reference(StrictModel):
    """An external citation for the scenario (papers, CVEs, OWASP, the guard)."""

    url: str
    title: str = ""


class Execution(StrictModel):
    """Runtime parameters controlling how a scenario is executed."""

    timeout_seconds: float = Field(default=60.0, gt=0)
    num_runs: int = Field(default=5, ge=1)
    flaky_threshold: float = Field(default=0.4, gt=0, le=1.0)


class Scenario(StrictModel):
    """A complete adversarial scenario — the root of the YAML schema."""

    id: str
    name: str
    description: str = ""
    owasp_category: OwaspCategory
    severity: Severity
    difficulty: Difficulty = Difficulty.BASIC
    tags: list[str] = Field(default_factory=list)

    setup: Setup
    attack: Attack
    success_criteria: SuccessCriteria

    mitigations: list[str] = Field(default_factory=list)
    references: list[Reference] = Field(default_factory=list)
    execution: Execution = Field(default_factory=Execution)

    @model_validator(mode="after")
    def _check_id_prefix(self) -> Scenario:
        """The scenario id should start with its OWASP category (e.g. ``ASI01-001``)."""
        prefix = self.owasp_category.value
        if not self.id.startswith(prefix):
            raise ValueError(
                f"scenario id {self.id!r} must start with its owasp_category {prefix!r}"
            )
        return self


class ScenarioLoadError(Exception):
    """Raised when a scenario file cannot be parsed or fails validation.

    Carries the offending ``path`` so the CLI can render an actionable message.
    """

    def __init__(self, path: Path, message: str) -> None:
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message}")


class ScenarioLoader:
    """Discovers and validates scenario YAML files from a directory tree."""

    def __init__(self, root: Path | str) -> None:
        """Initialize the loader.

        Args:
            root: Directory to search recursively, or a single ``.yaml`` file.
        """
        self.root = Path(root)

    def discover(self) -> list[Path]:
        """Return all scenario YAML file paths under ``root``, sorted.

        Returns:
            Sorted list of ``.yaml`` / ``.yml`` paths. A single file root yields
            just that file.
        """
        if self.root.is_file():
            return [self.root]
        files = [
            p
            for p in self.root.rglob("*")
            if p.is_file() and p.suffix.lower() in {".yaml", ".yml"}
        ]
        return sorted(files)

    def load_file(self, path: Path) -> Scenario:
        """Parse and validate a single scenario file.

        Args:
            path: Path to a scenario YAML file.

        Returns:
            The validated :class:`Scenario`.

        Raises:
            ScenarioLoadError: If the YAML is malformed or fails schema validation.
        """
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise ScenarioLoadError(path, f"invalid YAML: {exc}") from exc
        if not isinstance(raw, dict):
            raise ScenarioLoadError(path, "scenario file must contain a YAML mapping")
        try:
            return Scenario.model_validate(raw)
        except ValidationError as exc:
            raise ScenarioLoadError(path, _format_validation_error(exc)) from exc

    def load_all(self) -> list[Scenario]:
        """Load and validate every discovered scenario.

        Returns:
            Validated scenarios sorted by id.

        Raises:
            ScenarioLoadError: On the first file that fails to load or validate.
        """
        scenarios = [self.load_file(p) for p in self.discover()]
        scenarios.sort(key=lambda s: s.id)
        return scenarios


def bundled_scenarios_dir() -> Path:
    """Return the directory of scenarios shipped inside the installed package."""
    return Path(__file__).resolve().parent.parent / "scenarios"


def _format_validation_error(exc: ValidationError) -> str:
    """Render a pydantic ValidationError as a compact, field-oriented message."""
    parts: list[str] = []
    for err in exc.errors():
        loc = ".".join(str(item) for item in err["loc"]) or "<root>"
        parts.append(f"{loc}: {err['msg']}")
    return "; ".join(parts)
