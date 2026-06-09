"""Framework target adapters (LangGraph, CrewAI, MCP) and their registry."""

from __future__ import annotations

from aion_redteam.core.target import Target, TargetError

# Adapter name -> (module path, class name, extra to install). Imported lazily so the
# core package has no hard dependency on any framework.
_ADAPTERS: dict[str, tuple[str, str, str]] = {
    "langgraph": ("aion_redteam.adapters.langgraph", "LangGraphTarget", "langgraph"),
}


def available_adapters() -> list[str]:
    """Return the names of registered adapters."""
    return sorted(_ADAPTERS)


def get_adapter(name: str) -> Target:
    """Instantiate the target adapter registered under ``name``.

    Args:
        name: Adapter name (e.g. ``"langgraph"``).

    Returns:
        A fresh, unloaded :class:`Target` instance.

    Raises:
        TargetError: If the adapter is unknown or its optional dependency is missing.
    """
    if name not in _ADAPTERS:
        known = ", ".join(available_adapters())
        raise TargetError(f"unknown adapter {name!r}. Available: {known}")
    module_path, class_name, extra = _ADAPTERS[name]
    try:
        module = __import__(module_path, fromlist=[class_name])
    except ImportError as exc:
        raise TargetError(
            f"adapter {name!r} requires extra dependencies. "
            f'Install with: pip install "aion-redteam[{extra}]"'
        ) from exc
    return getattr(module, class_name)()


__all__ = ["available_adapters", "get_adapter"]
