"""Documentation — AI-Assisted Workflow Authoring."""

import re
from pathlib import Path

import streamlit as st

DOCS_PATH = Path(__file__).parent.parent / "docs" / "documentation.md"

# Native Graphviz (DOT) equivalents of the Mermaid diagrams in the markdown.
# These render via st.graphviz_chart() — no iframes, proper theme integration.

GRAPHVIZ_DIAGRAMS: list[str] = [
    # Diagram 1 — Architecture Overview
    """
    digraph architecture {
        rankdir=LR
        graph [bgcolor=transparent, fontname="Arial", pad="0.3"]
        node [fontname="Arial", fontsize=11, style="filled,rounded", shape=box, margin="0.15,0.08"]
        edge [fontname="Arial", fontsize=9]

        subgraph cluster_user {
            label="User"
            style="dashed,rounded"
            color="#888"
            fontcolor="#ccc"
            U [label="👤  Browser", fillcolor="#2d2d4a", fontcolor="#e0e0e0"]
        }

        subgraph cluster_azure {
            label="Azure Subscription"
            style="dashed,rounded"
            color="#4a6fa5"
            fontcolor="#8ab4f8"

            subgraph cluster_aca {
                label="Container Apps Environment"
                style="dashed,rounded"
                color="#666"
                fontcolor="#aaa"
                APP [label="🐳  Streamlit App\\n(Container App)", fillcolor="#1a3a5c", fontcolor="#e0e0e0"]
            }

            ACR [label="📦  Azure Container\\nRegistry", fillcolor="#1a4a2e", fontcolor="#e0e0e0"]
            LOG [label="📊  Log Analytics\\nWorkspace", fillcolor="#3a1a4a", fontcolor="#e0e0e0"]
            OAI [label="🧠  Azure OpenAI\\n(GPT-4o-mini)", fillcolor="#4a3a1a", fontcolor="#e0e0e0"]
        }

        U -> APP [label="HTTPS", color="#8ab4f8", fontcolor="#8ab4f8"]
        APP -> OAI [label="Managed Identity\\n(TokenCredential)", color="#f0b860", fontcolor="#f0b860"]
        APP -> LOG [label="stdout / stderr", style=dashed, color="#888", fontcolor="#aaa"]
        ACR -> APP [label="Image pull", style=dashed, color="#888", fontcolor="#aaa"]
    }
    """,
    # Diagram 2 — Agent Pipeline
    """
    digraph pipeline {
        rankdir=LR
        graph [bgcolor=transparent, fontname="Arial", pad="0.3"]
        node [fontname="Arial", fontsize=11, style="filled,rounded", shape=box, margin="0.15,0.08"]
        edge [fontname="Arial", fontsize=9]

        A [label="👤  User Prompt", fillcolor="#2d2d4a", fontcolor="#e0e0e0"]
        B [label="🧠  Intent Parser\\nNL → JSON", fillcolor="#1a3a5c", fontcolor="#e0e0e0"]
        C [label="📝  XML Generator\\nJSON → XML", fillcolor="#4a3a1a", fontcolor="#e0e0e0"]
        D [label="✅  Validator\\nXSD + Semantic", shape=diamond, fillcolor="#1a4a2e", fontcolor="#e0e0e0"]
        E [label="🔧  Repair Agent", fillcolor="#4a1a2e", fontcolor="#e0e0e0"]
        F [label="📄  BPMN 2.0\\nor BPEL 2.0", fillcolor="#2d2d4a", fontcolor="#e0e0e0"]

        A -> B [color="#8ab4f8"]
        B -> C [color="#8ab4f8"]
        C -> D [color="#8ab4f8"]
        D -> F [label="Valid", color="#66bb6a", fontcolor="#66bb6a"]
        D -> E [label="Invalid", color="#ef5350", fontcolor="#ef5350"]
        E -> C [label="Retry (≤ 3)", color="#ffa726", fontcolor="#ffa726"]
        E -> F [label="Max retries", style=dashed, color="#888", fontcolor="#aaa"]
    }
    """,
    # Diagram 3 — Data Flow (sequence-style, rendered as vertical flow)
    """
    digraph dataflow {
        rankdir=TB
        graph [bgcolor=transparent, fontname="Arial", pad="0.3"]
        node [fontname="Arial", fontsize=10, style="filled,rounded", shape=box, margin="0.12,0.06"]
        edge [fontname="Arial", fontsize=9]

        U [label="👤  User (Browser)", fillcolor="#2d2d4a", fontcolor="#e0e0e0"]
        App [label="🖥️  Streamlit App", fillcolor="#1a3a5c", fontcolor="#e0e0e0"]
        IP [label="🧠  Intent Parser (LLM)", fillcolor="#1a3a5c", fontcolor="#e0e0e0"]
        SG [label="📝  XML Generator (LLM)", fillcolor="#4a3a1a", fontcolor="#e0e0e0"]
        V [label="✅  Validator", fillcolor="#1a4a2e", fontcolor="#e0e0e0"]
        RA [label="🔧  Repair Agent (LLM)", fillcolor="#4a1a2e", fontcolor="#e0e0e0"]

        U -> App [label="NL prompt", color="#8ab4f8", fontcolor="#8ab4f8"]
        App -> IP [label="System prompt + user text", color="#8ab4f8", fontcolor="#8ab4f8"]
        IP -> App [label="Structured JSON spec", style=dashed, color="#66bb6a", fontcolor="#66bb6a"]
        App -> SG [label="JSON + format prompt", color="#8ab4f8", fontcolor="#8ab4f8"]
        SG -> App [label="Draft XML", style=dashed, color="#66bb6a", fontcolor="#66bb6a"]
        App -> V [label="XML string", color="#8ab4f8", fontcolor="#8ab4f8"]
        V -> App [label="✅ Pass  or  ❌ Errors", style=dashed, color="#ffa726", fontcolor="#ffa726"]
        App -> RA [label="XML + errors (if invalid)", color="#ef5350", fontcolor="#ef5350"]
        RA -> V [label="Repaired XML (≤ 3×)", color="#ffa726", fontcolor="#ffa726"]
        App -> U [label="Final XML + diagram", style=dashed, color="#66bb6a", fontcolor="#66bb6a"]
    }
    """,
    # Diagram 4 — RBAC Identity
    """
    digraph rbac {
        rankdir=LR
        graph [bgcolor=transparent, fontname="Arial", pad="0.3"]
        node [fontname="Arial", fontsize=11, style="filled,rounded", shape=box, margin="0.15,0.08"]
        edge [fontname="Arial", fontsize=9]

        MI [label="🔐  Managed Identity\\n(Container App)", fillcolor="#1a4a2e", fontcolor="#e0e0e0"]
        OAI [label="🧠  Azure OpenAI", fillcolor="#4a3a1a", fontcolor="#e0e0e0"]

        MI -> OAI [label="RBAC: Cognitive Services\\nOpenAI User", color="#8ab4f8", fontcolor="#8ab4f8"]
    }
    """,
]


def render_markdown_with_diagrams(md_text: str):
    """Render markdown, replacing Mermaid blocks with native Graphviz charts."""
    parts = re.split(r"```mermaid\s*\n(.*?)```", md_text, flags=re.DOTALL)
    diagram_index = 0
    for i, part in enumerate(parts):
        if i % 2 == 0:
            if part.strip():
                st.markdown(part, unsafe_allow_html=True)
        else:
            if diagram_index < len(GRAPHVIZ_DIAGRAMS):
                st.graphviz_chart(GRAPHVIZ_DIAGRAMS[diagram_index])
            diagram_index += 1


# ── Main ──────────────────────────────────────────────────────────────────────

if DOCS_PATH.exists():
    md_content = DOCS_PATH.read_text(encoding="utf-8")
    render_markdown_with_diagrams(md_content)
else:
    st.error(f"Documentation file not found: `{DOCS_PATH}`")

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
