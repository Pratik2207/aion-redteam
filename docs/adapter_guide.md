# Building an adapter

An **adapter** teaches aion-redteam how to drive a particular agent framework. It
implements the `Target` abstract base class (`aion_redteam.core.target.Target`).

## The lifecycle

The runner drives every target through the same sequence, once per repetition:

```
reset() -> configure(setup) -> inject(payload, injection_point) -> execute(input) -> get_response()
```

| Method | Responsibility |
|--------|----------------|
| `load(config)`        | Locate and load the user's real agent. Raise `TargetError` on failure. |
| `configure(setup)`    | Apply legitimate setup (system prompt, tools). Default no-op. |
| `inject(payload, point)` | Stage the attack payload for the given injection point. |
| `execute(input)`      | Run the agent on the benign input, applying the staged injection. |
| `get_response()`      | Return a `TargetResponse` (final output, tool calls, trace, error, duration). |
| `reset()`             | Clear per-run state before the next repetition. |

Agent **runtime** errors should be captured in `TargetResponse.error` (so the run is
classified `ERROR`), not raised. Raise `TargetError` only for load/config problems.

## Targets exercise the real agent

Adapters must run the genuine agent — real model calls, real tools. Mocking belongs in
unit tests of individual components, never on the execution path. Tests of adapter
*plumbing* may use a deterministic real graph as an LLM stand-in, but end-to-end scenario
runs and demos always use a live model.

## The LangGraph adapter (reference)

`LangGraphTarget` wraps a compiled LangGraph graph:

- **Discovery** — `load()` imports the target file and finds a compiled graph by explicit
  `attribute`, then by candidate names (`graph`, `app`, `agent`, `workflow`), then by
  factory functions (`build_graph`, `make_graph`, `get_graph`, `build_agent`).
- **Invocation** — calls `graph.ainvoke({"messages": [...]})` (the `MessagesState`
  convention; override the key with `messages_key` in config).
- **Injection encoding** — each injection point is woven into the message list:

  | Injection point        | How it reaches a single-node agent |
  |------------------------|------------------------------------|
  | `system_prompt`        | replaces the system message |
  | `user_message`         | appended to the user message |
  | `tool_output`          | added as a labeled `[Tool output]` block |
  | `rag_document`         | added as a labeled `[Retrieved document]` block |
  | `memory`               | added as a labeled `[Recalled memory]` block |
  | `inter_agent_message`  | added as a labeled `[Message from peer agent]` block |

  On single-node agents these channels collapse into the prompt; on multi-node graphs a
  future adapter revision can route them to the real node (a tool result, a retriever,
  the memory store). Document any such limitation in your adapter.

## Registering an adapter

Add it to `_ADAPTERS` in `aion_redteam/adapters/__init__.py`:

```python
_ADAPTERS = {
    "langgraph": ("aion_redteam.adapters.langgraph", "LangGraphTarget", "langgraph"),
    "crewai": ("aion_redteam.adapters.crewai", "CrewAITarget", "crewai"),
}
```

The third tuple element is the optional-dependency extra; it is named in the error
message when the framework isn't installed.
