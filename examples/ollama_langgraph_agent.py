"""A real, fully local LangGraph agent backed by Ollama — used as a red-team target.

No API key required: this talks to your local Ollama server. Use it as a template for
pointing aion-redteam at your own Ollama-backed LangGraph agent.

Requirements:
    pip install "aion-redteam[langgraph]" langchain-ollama
    ollama serve            # (usually already running)
    ollama pull llama3.2    # or any model you have

    export AION_OLLAMA_MODEL=llama3.2                 # optional, defaults to llama3.2
    export OLLAMA_BASE_URL=http://localhost:11434     # optional

Run it:
    aion-redteam run --target examples/ollama_langgraph_agent.py --adapter langgraph

The harness discovers the module-level ``graph`` (a compiled ``StateGraph``).
"""

from __future__ import annotations

import os

from langchain_ollama import ChatOllama
from langgraph.graph import END, START, MessagesState, StateGraph

MODEL = os.environ.get("AION_OLLAMA_MODEL", "llama3.2")
BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
SYSTEM_PROMPT = "You are a helpful coding assistant."


def assistant(state: MessagesState) -> dict[str, list]:
    """Single LLM node: send the conversation to the local Ollama model."""
    llm = ChatOllama(model=MODEL, base_url=BASE_URL, temperature=0)
    messages = state["messages"]
    # If the harness didn't supply a system message, prepend the default one.
    if not any(getattr(m, "type", "") == "system" for m in messages):
        from langchain_core.messages import SystemMessage

        messages = [SystemMessage(content=SYSTEM_PROMPT), *messages]
    return {"messages": [llm.invoke(messages)]}


def build_graph():
    """Build and compile the agent graph. Returns a compiled ``StateGraph``."""
    builder = StateGraph(MessagesState)
    builder.add_node("assistant", assistant)
    builder.add_edge(START, "assistant")
    builder.add_edge("assistant", END)
    return builder.compile()


# Discovered by the LangGraph adapter.
graph = build_graph()


if __name__ == "__main__":
    from langchain_core.messages import HumanMessage

    result = graph.invoke(
        {"messages": [HumanMessage(content="Say hello in one short sentence.")]}
    )
    print(result["messages"][-1].content)
