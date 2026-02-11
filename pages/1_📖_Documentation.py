"""Documentation page for AI-Assisted Workflow Authoring."""

import streamlit as st

st.set_page_config(page_title="Documentation", page_icon="📖", layout="wide")


def render_mermaid(mermaid_code: str, height: int = 500):
    """Render a Mermaid diagram using the Mermaid JS CDN."""
    html = f"""
    <div class="mermaid" style="display: flex; justify-content: center;">
    {mermaid_code}
    </div>
    <script type="module">
        import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';
        mermaid.initialize({{ startOnLoad: true, theme: 'neutral' }});
    </script>
    """
    st.html(html)


# ── Title ──────────────────────────────────────────────────────────────────────
st.title("📖 Documentation")

# ── 1. Overview ────────────────────────────────────────────────────────────────
st.header("1. Overview")

st.markdown(
    """
**AI-Assisted Workflow Authoring** transforms natural language descriptions into
valid **BPMN 2.0** or **WS-BPEL 2.0** XML using a sequential agent pipeline
with iterative validation and repair.

#### Problem Statement

Enterprise integration platforms require deep
platform expertise to author integrations. Users must translate business
scenarios into detailed process graphs and XML definitions through manual,
error-prone steps. LLMs lack native understanding of custom XML grammars and
semantic constraints.

This tool **bridges the gap** by combining LLM-based code generation with
deterministic validation and iterative repair — preserving correctness,
debuggability, and human control.

> 📐 Built on the
> [Sequential Orchestration Pattern](https://learn.microsoft.com/en-us/agent-framework/user-guide/workflows/orchestrations/sequential)
> from Microsoft's AI Agent Design Patterns.
"""
)

# ── 2. How It Works — Pipeline Walkthrough ─────────────────────────────────────
st.header("2. How It Works — Pipeline Walkthrough")

st.markdown(
    """
When a user submits a natural language prompt, the following stages execute
sequentially:

1. 🧠 **Intent Parsing** — The user's natural language description is sent to an
   LLM (Azure OpenAI) with a system prompt that instructs it to extract a
   structured JSON workflow specification. The JSON schema includes activities
   (tasks, events, gateways), sequence flows, variables, and partner links.

2. 📝 **XML Generation** — The structured JSON is passed to a second LLM call
   with format-specific instructions (BPMN 2.0 or WS-BPEL 2.0). The LLM
   generates the complete XML document following the target specification.

3. ✅ **Validation** — The generated XML is validated using two methods:
   - **XSD Schema Validation**: Checks structural correctness against simplified
     BPMN/BPEL schemas
   - **Semantic Validation**: Checks workflow correctness — reachability
     analysis, completeness checks, proper start/end events

4. 🔧 **Repair Loop** (if needed) — If validation fails, the XML and error
   messages are sent to a repair agent LLM. The repaired XML goes back through
   validation. This loops up to 3 times.

5. 📄 **Output** — The final validated XML is presented to the user with syntax
   highlighting, a visual workflow diagram, and download options.
"""
)

# ── 3. Architecture Diagram ────────────────────────────────────────────────────
st.header("3. Architecture Diagram")

render_mermaid(
    """
flowchart LR
    subgraph Input
        A[👤 User Prompt]
    end
    subgraph Pipeline ["Sequential Agent Pipeline"]
        B[🧠 Intent Parser<br/>NL → JSON]
        C[📝 Schema Generator<br/>JSON → XML]
        D{✅ Validator<br/>XSD + Semantic}
        E[🔧 Repair Agent<br/>Fix Errors]
    end
    subgraph Output
        F[📄 BPMN 2.0<br/>or BPEL 2.0]
    end
    A --> B
    B --> C
    C --> D
    D -->|Valid| F
    D -->|Invalid| E
    E -->|Retry ≤3| C
    E -->|Max Retries| F
    style B fill:#e1f5fe
    style C fill:#fff3e0
    style D fill:#e8f5e9
    style E fill:#fce4ec
"""
)

# ── 4. Data Flow — Sequence Diagram ────────────────────────────────────────────
st.header("4. Data Flow — Sequence Diagram")

render_mermaid(
    """
sequenceDiagram
    participant U as User
    participant App as Streamlit App
    participant IP as Intent Parser (LLM)
    participant SG as Schema Generator (LLM)
    participant V as Validator (Deterministic)
    participant RA as Repair Agent (LLM)

    U->>App: Natural language prompt
    App->>IP: Parse intent
    IP-->>App: Structured JSON (WorkflowSpec)
    App->>SG: Generate XML from JSON
    SG-->>App: Draft XML
    App->>V: Validate XML (XSD + Semantic)
    alt Valid
        V-->>App: ✅ Validation passed
        App-->>U: Final XML + Diagram
    else Invalid
        V-->>App: ❌ Errors found
        loop Up to 3 repair attempts
            App->>RA: XML + Errors
            RA-->>App: Repaired XML
            App->>V: Re-validate
        end
        App-->>U: Best result + any remaining errors
    end
"""
)

# ── 5. Validation & Repair Loop ────────────────────────────────────────────────
st.header("5. Validation & Repair Loop")

st.markdown(
    """
The validation stage combines **XSD schema validation** (structural
correctness) with **semantic checks** (workflow correctness). If either fails,
the repair agent attempts to fix the XML automatically.
"""
)

render_mermaid(
    """
flowchart TD
    A[Draft XML] --> B[XSD Validation]
    B -->|Pass| C[Semantic Checks]
    B -->|Fail| D[Collect XSD Errors]
    C -->|Pass| E[✅ Valid XML]
    C -->|Fail| F[Collect Semantic Errors]
    D --> G{Attempts < 3?}
    F --> G
    G -->|Yes| H[Repair Agent LLM]
    G -->|No| I[⚠️ Return Best Effort]
    H --> J[Generate Fixed XML]
    J --> B

    style E fill:#c8e6c9
    style I fill:#fff9c4
    style H fill:#fce4ec
"""
)

# ── 6. Intermediate JSON Schema ────────────────────────────────────────────────
st.header("6. Intermediate JSON Schema")

st.markdown(
    """
The pipeline uses **Pydantic models** as the intermediate representation
between the intent parser and the XML generator. This decouples natural
language understanding from XML serialisation.
"""
)

st.subheader("Key Models")

st.code(
    '''
from enum import Enum
from pydantic import BaseModel, Field

class ActivityType(str, Enum):
    """Supported BPMN/BPEL activity types."""
    START_EVENT = "startEvent"
    END_EVENT = "endEvent"
    TASK = "task"
    SERVICE_TASK = "serviceTask"
    USER_TASK = "userTask"
    SCRIPT_TASK = "scriptTask"
    EXCLUSIVE_GATEWAY = "exclusiveGateway"
    PARALLEL_GATEWAY = "parallelGateway"
    RECEIVE = "receive"
    REPLY = "reply"
    INVOKE = "invoke"
    ASSIGN = "assign"
    IF = "if"
    WHILE = "while"
    SEQUENCE = "sequence"

class Activity(BaseModel):
    id: str                          # Unique identifier
    type: ActivityType               # Activity type
    name: str | None = None          # Human-readable name
    operation: str | None = None     # Operation/service to invoke
    condition: str | None = None     # Condition expression

class SequenceFlow(BaseModel):
    id: str | None = None            # Flow identifier
    source: str = Field(alias="from")  # Source activity ID
    target: str = Field(alias="to")    # Target activity ID
    name: str | None = None          # Flow label (e.g. "Yes", "No")
    condition: str | None = None     # Condition expression

class Variable(BaseModel):
    name: str                        # Variable name
    type: str | None = None          # e.g. "string", "integer"

class PartnerLink(BaseModel):
    name: str                        # Partner link name
    partner_link_type: str           # Partner link type reference
    my_role: str | None = None
    partner_role: str | None = None

class Workflow(BaseModel):
    """Intermediate workflow representation."""
    name: str
    description: str | None = None
    namespace: str = "http://example.com/workflow"
    activities: list[Activity] = []
    flows: list[SequenceFlow] = []
    variables: list[Variable] = []
    partner_links: list[PartnerLink] = []

class WorkflowSpec(BaseModel):
    """Top-level container for workflow specification."""
    workflow: Workflow
''',
    language="python",
)

# ── 7. Design Decisions ───────────────────────────────────────────────────────
st.header("7. Design Decisions")

with st.expander("**Why Intermediate JSON?**"):
    st.markdown(
        """
- **Reduces LLM hallucination** — Generating structured JSON is easier for an
  LLM than generating syntactically valid XML with namespaces.
- **Easier to validate** — JSON can be validated with Pydantic before XML
  generation even starts.
- **Decouples intent from syntax** — The same JSON can produce BPMN *or* BPEL
  output, keeping the intent parser format-agnostic.
"""
    )

with st.expander("**Why Iterative Repair?**"):
    st.markdown(
        """
- LLMs don't always produce valid XML on the first try, especially for complex
  schemas with namespaces and cross-references.
- **Deterministic validation** (XSD + semantic checks) catches errors that the
  LLM cannot self-detect.
- Feeding error messages back to the LLM as repair context produces targeted
  fixes rather than full regeneration.
"""
    )

with st.expander("**Why Human-in-the-Loop?**"):
    st.markdown(
        """
- All intermediate steps (JSON spec, draft XML, validation results) are visible
  to the user.
- Users can **download and edit** the generated XML at any stage.
- Clear error messages and suggestions help users understand *what* went wrong
  and *why*.
"""
    )

with st.expander("**Why Sequential Orchestration?**"):
    st.markdown(
        """
- Each stage has **clear inputs and outputs** — easy to test and debug
  independently.
- Follows
  [Microsoft's AI Agent Design Patterns](https://learn.microsoft.com/en-us/agent-framework/user-guide/workflows/orchestrations/sequential)
  for agent orchestration.
- Simpler to reason about than graph-based or event-driven approaches; the
  linear flow matches how a human expert would approach the task.
"""
    )

# ── 8. References ─────────────────────────────────────────────────────────────
st.header("8. References")

st.markdown(
    """
| Resource | Link |
|----------|------|
| Microsoft AI Agent Design Patterns | [Sequential Orchestration](https://learn.microsoft.com/en-us/agent-framework/user-guide/workflows/orchestrations/sequential) |
| BPMN 2.0 Specification | [OMG BPMN 2.0](https://www.omg.org/spec/BPMN/2.0/) |
| WS-BPEL 2.0 Specification | [OASIS WS-BPEL 2.0](http://docs.oasis-open.org/wsbpel/2.0/OS/wsbpel-v2.0-OS.html) |
| Automated BPMN Generation from NL (arXiv) | [arXiv:2509.24592](https://arxiv.org/abs/2509.24592) |
| LLM-Driven Process Modelling (Springer) | [Springer Chapter](https://link.springer.com/chapter/10.1007/978-3-031-70418-5_11) |
| Process Model Generation with LLMs (CEUR-WS) | [CEUR-WS Paper](https://ceur-ws.org/Vol-3936/paper-11.pdf) |
"""
)

# ── Footer ────────────────────────────────────────────────────────────────────
st.divider()
st.markdown(
    """
<div style='text-align: center; color: #666;'>
    <small>
        Built with Microsoft Agent Framework | Sequential Orchestration Pattern<br>
        <a href="https://learn.microsoft.com/en-us/agent-framework/user-guide/workflows/orchestrations/sequential">
            AI Agent Orchestration Patterns
        </a>
    </small>
</div>
""",
    unsafe_allow_html=True,
)
