"""LangGraph implementation of the workflow authoring pipeline for comparison.

This module demonstrates the same sequential agent pattern using LangGraph
instead of Microsoft Agent Framework, showing the differences in approach.
"""

import json
from typing import TypedDict

from dotenv import load_dotenv

from .models import (
    PipelineState,
    WorkflowSpec,
    WORKFLOW_JSON_SCHEMA,
)
from .prompts import (
    INTENT_PARSER_SYSTEM,
    SCHEMA_GENERATOR_BPMN_SYSTEM,
    SCHEMA_GENERATOR_BPEL_SYSTEM,
)
from .validation import validate_workflow_xml, pretty_print_xml

load_dotenv()

# Check for LangGraph availability
try:
    from langchain_openai import ChatOpenAI
    from langgraph.graph import StateGraph, END  # noqa: F401

    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    print("LangGraph not available. Install with: pip install langgraph langchain-openai")


class GraphState(TypedDict):
    """State for LangGraph pipeline."""

    user_input: str
    output_format: str
    workflow_json: str | None
    draft_xml: str | None
    validation_errors: list[str]
    final_xml: str | None
    repair_attempts: int
    max_repairs: int
    error_message: str | None


def create_langgraph_pipeline():
    """Create the LangGraph workflow pipeline."""

    if not LANGGRAPH_AVAILABLE:
        raise RuntimeError("LangGraph is not installed")

    # Initialize LLM (requires OPENAI_API_KEY)
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2)

    # Define nodes
    def parse_intent(state: GraphState) -> GraphState:
        """Node: Parse natural language to JSON."""
        schema_json = json.dumps(WORKFLOW_JSON_SCHEMA, indent=2)
        prompt = INTENT_PARSER_SYSTEM.format(schema=schema_json)

        messages = [
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": f"Convert this workflow description to JSON:\n\n{state['user_input']}",
            },
        ]

        response = llm.invoke(messages)
        content = response.content.strip()

        # Clean up markdown
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]

        try:
            # Validate JSON
            parsed = json.loads(content)
            state["workflow_json"] = json.dumps(parsed)
        except json.JSONDecodeError as e:
            state["error_message"] = f"Failed to parse JSON: {e}"

        return state

    def generate_xml(state: GraphState) -> GraphState:
        """Node: Generate XML from JSON spec."""
        if state.get("error_message") or not state.get("workflow_json"):
            return state

        prompt = (
            SCHEMA_GENERATOR_BPMN_SYSTEM
            if state["output_format"] == "bpmn"
            else SCHEMA_GENERATOR_BPEL_SYSTEM
        )

        messages = [
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": f"Generate {state['output_format'].upper()} XML for this workflow:\n\n{state['workflow_json']}",
            },
        ]

        response = llm.invoke(messages)
        content = response.content.strip()

        # Clean up markdown
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("xml"):
                content = content[3:]
            content = content.strip()

        state["draft_xml"] = content
        return state

    def validate_xml(state: GraphState) -> GraphState:
        """Node: Validate the generated XML."""
        if state.get("error_message") or not state.get("draft_xml"):
            return state

        result = validate_workflow_xml(state["draft_xml"], state["output_format"])

        state["validation_errors"] = [e.message for e in result.errors]

        if result.valid:
            state["final_xml"] = pretty_print_xml(state["draft_xml"])

        return state

    def repair_xml(state: GraphState) -> GraphState:
        """Node: Attempt to repair invalid XML."""
        if state.get("error_message"):
            return state

        if not state.get("validation_errors"):
            return state

        state["repair_attempts"] = state.get("repair_attempts", 0) + 1

        if state["repair_attempts"] > state.get("max_repairs", 3):
            state["error_message"] = "Max repair attempts reached"
            return state

        errors_str = "\n".join(f"- {e}" for e in state["validation_errors"])

        messages = [
            {
                "role": "system",
                "content": "You are an XML repair specialist. Fix the validation errors in the XML while preserving the workflow structure.",
            },
            {
                "role": "user",
                "content": f"""Fix this {state["output_format"].upper()} XML:

Current XML:
{state["draft_xml"]}

Validation errors:
{errors_str}

Return only the corrected XML.""",
            },
        ]

        response = llm.invoke(messages)
        content = response.content.strip()

        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("xml"):
                content = content[3:]
            content = content.strip()

        state["draft_xml"] = content
        return state

    def should_repair(state: GraphState) -> str:
        """Conditional edge: decide whether to repair or end."""
        if state.get("error_message"):
            return "end"
        if not state.get("validation_errors"):
            return "end"
        if state.get("repair_attempts", 0) >= state.get("max_repairs", 3):
            return "end"
        return "repair"

    # Build the graph
    workflow = StateGraph(GraphState)

    # Add nodes
    workflow.add_node("parse_intent", parse_intent)
    workflow.add_node("generate_xml", generate_xml)
    workflow.add_node("validate_xml", validate_xml)
    workflow.add_node("repair_xml", repair_xml)

    # Add edges (sequential flow)
    workflow.set_entry_point("parse_intent")
    workflow.add_edge("parse_intent", "generate_xml")
    workflow.add_edge("generate_xml", "validate_xml")

    # Conditional edge for repair loop
    workflow.add_conditional_edges(
        "validate_xml", should_repair, {"repair": "repair_xml", "end": END}
    )

    # After repair, re-validate
    workflow.add_edge("repair_xml", "validate_xml")

    return workflow.compile()


async def run_langgraph_pipeline(
    user_input: str, output_format: str = "bpmn", max_repairs: int = 3
) -> PipelineState:
    """Run the LangGraph pipeline and return results in the same format as the Agent Framework version."""

    if not LANGGRAPH_AVAILABLE:
        raise RuntimeError("LangGraph is not installed")

    graph = create_langgraph_pipeline()

    initial_state: GraphState = {
        "user_input": user_input,
        "output_format": output_format,
        "workflow_json": None,
        "draft_xml": None,
        "validation_errors": [],
        "final_xml": None,
        "repair_attempts": 0,
        "max_repairs": max_repairs,
        "error_message": None,
    }

    # Run the graph
    result = graph.invoke(initial_state)

    # Convert to PipelineState for consistency
    state = PipelineState(
        user_input=user_input, output_format=output_format, max_repairs=max_repairs
    )

    if result.get("workflow_json"):
        try:
            state.workflow_json = WorkflowSpec.model_validate(json.loads(result["workflow_json"]))
        except Exception:
            pass

    state.draft_xml = result.get("draft_xml")
    state.final_xml = result.get("final_xml")
    state.repair_attempts = result.get("repair_attempts", 0)
    state.error_message = result.get("error_message")

    return state


# Comparison documentation
COMPARISON_DOC = """
# Microsoft Agent Framework vs LangGraph Comparison

## Architecture Approach

### Microsoft Agent Framework
- **Agent-centric**: Each stage is an autonomous agent with its own instructions
- **Context management**: Agents maintain conversation context automatically  
- **Backend flexibility**: Supports Azure AI, GitHub Copilot, and other backends
- **Async-first**: Native async/await pattern throughout

### LangGraph
- **Graph-centric**: Stages are nodes connected by edges
- **State management**: Explicit TypedDict state passed between nodes
- **Conditional routing**: Built-in support for conditional edges and loops
- **Visualization**: Can export graph structure for debugging

## Code Structure Comparison

### Agent Framework Pipeline
```python
class WorkflowPipeline:
    def __init__(self):
        self.intent_parser = create_agent("IntentParser", INTENT_PARSER_SYSTEM)
        self.bpmn_generator = create_agent("BPMNGenerator", SCHEMA_GENERATOR_BPMN_SYSTEM)
        # ...
    
    async def run(self, user_input):
        state = await self.parse_intent(state)
        state = await self.generate_xml(state)
        state = await self.validate_xml(state)
        # Manual repair loop
        while not valid and attempts < max:
            state = await self.repair_xml(state)
```

### LangGraph Pipeline
```python
workflow = StateGraph(GraphState)
workflow.add_node("parse_intent", parse_intent)
workflow.add_node("generate_xml", generate_xml)
workflow.add_node("validate_xml", validate_xml)
workflow.add_node("repair_xml", repair_xml)

workflow.add_edge("parse_intent", "generate_xml")
workflow.add_edge("generate_xml", "validate_xml")
workflow.add_conditional_edges("validate_xml", should_repair, {...})
workflow.add_edge("repair_xml", "validate_xml")
```

## Key Differences

| Aspect | Agent Framework | LangGraph |
|--------|-----------------|-----------|
| State | Pydantic models | TypedDict |
| Control flow | Manual loops | Graph edges |
| Loops | Python while | Conditional edges |
| Backend | Multi-provider | OpenAI/Anthropic |
| Debugging | Agent logs | Graph visualization |
| Enterprise | Azure integration | General purpose |

## When to Use Which

**Microsoft Agent Framework:**
- Building Microsoft 365 / Azure integrated agents
- Need multi-provider flexibility (Azure AI, GitHub Copilot)
- Enterprise deployments with compliance requirements
- Teams/Copilot channel deployment

**LangGraph:**
- Complex branching/looping workflows
- Need graph visualization for debugging
- Research/prototyping with visual tools
- LangSmith tracing integration
"""


if __name__ == "__main__":
    import asyncio

    async def demo():
        print("LangGraph Pipeline Demo")
        print("=" * 60)

        sample_input = """
        Create a simple order workflow:
        1. Receive order
        2. Validate order
        3. Process payment
        4. Ship order
        """

        try:
            result = await run_langgraph_pipeline(sample_input)
            print(f"\nResult: {'Success' if result.final_xml else 'Failed'}")
            if result.final_xml:
                print(result.final_xml[:500] + "...")
        except Exception as e:
            print(f"Error: {e}")

    asyncio.run(demo())
