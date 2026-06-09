---
name: New scenario proposal
about: Propose a new adversarial scenario
title: "[scenario] "
labels: scenario
---

**OWASP category**
Which ASI category does this attack target? (ASI01–ASI10)

**Attack vector**
What single attack does this scenario test? (One vector per scenario.)

**Injection point**
user_message | system_prompt | tool_output | rag_document | memory | inter_agent_message

**Proposed payload (sketch)**
The adversarial content (a canary token makes success criteria unambiguous).

**Success criteria**
How do we know the attack succeeded? (string_match / regex against agent_response, etc.)

**Severity**
low | medium | high | critical — and why.

**Mitigations**
How should a defender (e.g. aion-guard) stop this?

**References**
Papers, CVEs, or OWASP links that motivate this scenario.
