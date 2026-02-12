"""Workflow Authoring — main application page."""

import sys
import time
from pathlib import Path

import streamlit as st

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.pipeline import WorkflowPipeline
from src.models import PipelineState
from src.validation import pretty_print_xml
from src.utils import run_with_timeout, PipelineTimeout, DEFAULT_TIMEOUT
from src.logging_config import get_logger, get_recent_logs

# Initialize logger
logger = get_logger("ai_workflow.app")

# Initialize session state for persisting results
if "pipeline_state" not in st.session_state:
    st.session_state.pipeline_state = None
if "generation_count" not in st.session_state:
    st.session_state.generation_count = 0

# Custom CSS
st.markdown(
    """
<style>
    .stTextArea textarea {
        font-family: monospace;
    }
</style>
""",
    unsafe_allow_html=True,
)


# Sidebar
with st.sidebar:
    st.title("⚙️ Configuration")

    output_format = st.selectbox(
        "Output Format",
        ["bpmn", "bpel"],
        format_func=lambda x: "BPMN 2.0" if x == "bpmn" else "WS-BPEL 2.0",
    )

    use_github_copilot = st.checkbox(
        "Use GitHub Copilot",
        value=False,
        help="Use GitHub Copilot as the LLM backend (requires gh CLI auth)",
    )

    max_repairs = st.slider(
        "Max Repair Attempts",
        min_value=0,
        max_value=5,
        value=3,
        help="Maximum iterations for fixing validation errors",
    )

    timeout_seconds = st.slider(
        "LLM Timeout (seconds)",
        min_value=30,
        max_value=180,
        value=DEFAULT_TIMEOUT,
        help="Maximum time to wait for LLM response",
    )

    st.divider()

    st.subheader("📚 Example Prompts")

    examples = {
        "Order Processing": """Create an order processing workflow:
1. Receive order from customer
2. Validate the order details
3. Check inventory availability
4. If inventory is available, process payment
5. If inventory is not available, notify customer of backorder
6. Ship the order
7. Send confirmation email""",
        "Employee Onboarding": """Design an employee onboarding process:
1. Receive new hire notification from HR
2. Create user accounts (email, SSO)
3. Provision laptop and equipment
4. Schedule orientation meeting
5. Assign training modules
6. Send welcome package""",
        "Loan Approval": """Build a loan approval workflow:
1. Receive loan application
2. Verify applicant identity
3. Run credit check
4. If credit score is below 600, reject application
5. If credit score is 600-700, require manual review
6. If credit score is above 700, auto-approve
7. Generate loan documents
8. Send decision notification""",
        "Customer Support Ticket": """Create a customer support ticket workflow:
1. Receive support ticket from customer portal
2. Classify ticket priority (low, medium, high, critical)
3. Route to appropriate department based on category
4. If critical, page on-call engineer immediately
5. Assign to available agent with matching skills
6. Send acknowledgment email with ticket number
7. Track SLA timer based on priority
8. Escalate if SLA threshold is approaching
9. Close ticket and send satisfaction survey""",
        "Invoice Processing": """Design an invoice processing workflow:
1. Receive invoice via email or API
2. Extract invoice data using OCR
3. Validate vendor exists in system
4. Match invoice to purchase order
5. If amount differs by more than 5%, flag for review
6. Route for approval based on amount thresholds
7. Schedule payment according to terms
8. Update accounting system
9. Archive invoice document""",
        "Insurance Claim": """Build an insurance claim processing workflow:
1. Receive claim submission
2. Validate policy is active and covers claim type
3. Assign claim adjuster based on claim value
4. Request supporting documentation if missing
5. Run fraud detection checks
6. If fraud score is high, route to investigation team
7. Calculate payout based on policy terms
8. If payout exceeds $10,000, require manager approval
9. Process payment to claimant
10. Update claim status and notify customer""",
        "Data Pipeline ETL": """Create a data pipeline ETL workflow:
1. Trigger on schedule or file arrival
2. Extract data from source systems (API, database, files)
3. Validate data quality and completeness
4. Transform data according to business rules
5. If validation fails, quarantine bad records
6. Load data to data warehouse
7. Update data catalog metadata
8. Run downstream aggregation jobs
9. Send completion notification with metrics""",
        "Incident Response": """Design an IT incident response workflow:
1. Receive alert from monitoring system
2. Create incident ticket with severity level
3. If severity is P1, activate incident commander
4. Page on-call team members
5. Start incident bridge call
6. Diagnose root cause
7. Implement fix or workaround
8. Validate service restoration
9. Send customer communication
10. Schedule post-incident review
11. Update runbooks if needed""",
    }

    selected_example = st.selectbox("Load Example", [""] + list(examples.keys()))

    st.divider()

    st.markdown("""
    ### 🏗️ Architecture
    
    **Sequential Pipeline:**
    1. 🎯 Intent Parser (NL → JSON)
    2. 📝 Schema Generator (JSON → XML)
    3. ✅ Validator (XSD + semantic)
    4. 🔧 Repair Agent (fix errors)
    
    *Using Microsoft Agent Framework*
    """)

    st.divider()

    # Log viewer
    with st.expander("📋 Debug Logs", expanded=False):
        if st.button("🔄 Refresh Logs"):
            st.rerun()
        log_content = get_recent_logs(30)
        st.code(log_content, language=None)


# Main content
st.title("🔄 AI-Assisted Workflow Authoring")
st.markdown("""
Transform natural language descriptions into valid **BPMN 2.0** or **WS-BPEL 2.0** XML 
using a sequential agent pipeline with iterative validation and repair.
""")

# Input area
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("📝 Describe Your Workflow")

    # Pre-fill with example if selected
    default_text = examples.get(selected_example, "") if selected_example else ""

    user_input = st.text_area(
        "Natural language description",
        value=default_text,
        height=300,
        placeholder="""Describe your workflow in plain English. For example:

Create a customer support ticket workflow:
1. Customer submits ticket via web form
2. System categorizes the ticket (bug, feature request, question)
3. Assign to appropriate team based on category
4. Team member reviews and responds
5. If resolved, close ticket; otherwise, escalate
6. Send satisfaction survey""",
        label_visibility="collapsed",
    )

    generate_btn = st.button("🚀 Generate Workflow", type="primary", use_container_width=True)

with col2:
    st.subheader("ℹ️ How it works")
    st.markdown("""
    1. **Intent Parser** extracts workflow structure from your description
    2. **XML Generator** creates valid BPMN/BPEL markup  
    3. **Validator** checks against XSD schema + semantic rules
    4. **Repair Agent** fixes errors automatically (up to 3 attempts)
    """)

# Results section
st.divider()


def render_workflow_diagram(workflow):
    """Render a Graphviz diagram of the workflow."""
    dot_lines = [
        "digraph workflow {",
        "    rankdir=LR;",
        "    graph [dpi=72];",
        '    node [fontname="Arial", fontsize=10, margin="0.1,0.05"];',
        '    edge [fontname="Arial", fontsize=8];',
        "",
    ]

    for act in workflow.activities:
        label = act.name or act.id
        label = label.replace('"', '\\"')
        if act.type.value == "startEvent":
            dot_lines.append(
                f'    {act.id} [label="{label}", shape=circle, style=filled, fillcolor="#c8e6c9", width=0.4, height=0.4, fixedsize=true];'
            )
        elif act.type.value == "endEvent":
            dot_lines.append(
                f'    {act.id} [label="{label}", shape=doublecircle, style=filled, fillcolor="#ffcdd2", width=0.4, height=0.4, fixedsize=true];'
            )
        elif act.type.value in ["exclusiveGateway", "parallelGateway"]:
            dot_lines.append(
                f'    {act.id} [label="{label}", shape=diamond, style=filled, fillcolor="#fff9c4", width=0.5, height=0.5];'
            )
        elif act.type.value == "userTask":
            dot_lines.append(
                f'    {act.id} [label="{label}", shape=box, style="filled,rounded", fillcolor="#e3f2fd"];'
            )
        elif act.type.value == "serviceTask":
            dot_lines.append(
                f'    {act.id} [label="{label}", shape=box, style="filled,rounded", fillcolor="#f3e5f5"];'
            )
        else:
            dot_lines.append(
                f'    {act.id} [label="{label}", shape=box, style="filled,rounded", fillcolor="#e8eaf6"];'
            )

    dot_lines.append("")

    for flow in workflow.flows:
        label_attr = f' [label="{flow.name}"]' if flow.name else ""
        dot_lines.append(f"    {flow.source} -> {flow.target}{label_attr};")

    dot_lines.append("}")
    dot_code = "\n".join(dot_lines)

    try:
        st.graphviz_chart(dot_code, use_container_width=False)
    except Exception as e:
        st.error(f"Could not render diagram: {e}")
        st.code(dot_code, language="dot")

    with st.expander("📝 Mermaid Code (for export)"):
        mermaid_lines = ["graph LR"]
        for act in workflow.activities:
            shape_start = "((" if act.type.value in ["startEvent", "endEvent"] else "["
            shape_end = "))" if act.type.value in ["startEvent", "endEvent"] else "]"
            if act.type.value in ["exclusiveGateway", "parallelGateway"]:
                shape_start, shape_end = "{", "}"
            label = act.name or act.id
            mermaid_lines.append(f'    {act.id}{shape_start}"{label}"{shape_end}')
        for flow in workflow.flows:
            label = f"|{flow.name}|" if flow.name else ""
            mermaid_lines.append(f"    {flow.source} -->{label} {flow.target}")
        st.code("\n".join(mermaid_lines), language="mermaid")


if generate_btn and user_input.strip():
    # Log the start of generation
    logger.info(f"Starting generation #{st.session_state.generation_count + 1}")
    st.session_state.generation_count += 1

    # Clear previous results
    st.session_state.pipeline_state = None

    # Track elapsed time
    pipeline_start_time = time.time()

    pipeline = WorkflowPipeline(use_github_copilot=use_github_copilot)

    # Two-column layout: Pipeline Progress (left) | AI Thinking (right)
    col_progress, col_thinking = st.columns([1, 1])

    with col_progress:
        st.subheader("🔄 Pipeline Progress")

    with col_thinking:
        st.subheader("🧠 AI Thinking")
        # Simplified CSS for the thinking panel
        st.markdown(
            """
        <style>
        .thinking-container {
            background: #1e1e2e;
            border-radius: 8px;
            padding: 12px 16px;
            min-height: 180px;
            max-height: 250px;
            overflow-y: auto;
            font-family: 'Consolas', 'Monaco', monospace;
            font-size: 13px;
            border: 1px solid #3a3a5a;
        }
        .thinking-line {
            color: #a0a0a0;
            margin: 6px 0;
            line-height: 1.4;
        }
        .thinking-line.current {
            color: #00d084;
            font-weight: 500;
        }
        .thinking-status {
            margin-top: 12px;
            padding-top: 10px;
            border-top: 1px solid #3a3a5a;
            font-size: 12px;
        }
        .thinking-status.active {
            color: #ffc107;
        }
        .thinking-status.complete {
            color: #00d084;
        }
        .thinking-status.error {
            color: #ff6b6b;
        }
        </style>
        """,
            unsafe_allow_html=True,
        )
        thinking_placeholder = st.empty()
        thinking_log = []

    def render_thinking_panel(lines: list, status: str = "active", elapsed: float = 0):
        """Render the thinking panel with current status and elapsed time."""
        html_lines = []
        for i, line in enumerate(lines[-10:]):  # Show last 10 lines
            css_class = "thinking-line current" if i == len(lines[-10:]) - 1 else "thinking-line"
            html_lines.append(f'<div class="{css_class}">› {line}</div>')

        # Format elapsed time
        elapsed_str = f"{elapsed:.1f}s" if elapsed < 60 else f"{elapsed / 60:.1f}m"

        # Status indicator
        if status == "active":
            status_html = (
                f'<span class="thinking-status active">⏳ Processing... ({elapsed_str})</span>'
            )
        elif status == "complete":
            status_html = (
                f'<span class="thinking-status complete">✓ Complete ({elapsed_str})</span>'
            )
        else:
            status_html = f'<span class="thinking-status error">✗ {status}</span>'

        html = f"""
        <div class="thinking-container">
            {"".join(html_lines) if html_lines else '<div class="thinking-line">Initializing...</div>'}
            <div class="thinking-status">{status_html}</div>
        </div>
        """
        thinking_placeholder.markdown(html, unsafe_allow_html=True)

    def update_thinking(text: str, status: str = "active"):
        """Add text to the thinking log and update display."""
        thinking_log.append(text)
        elapsed = time.time() - pipeline_start_time
        render_thinking_panel(thinking_log, status, elapsed)

    # Final Results section - will update progressively
    st.divider()
    st.subheader("📊 Final Results")

    tab1, tab2, tab3, tab4 = st.tabs(
        ["📋 JSON Spec", "📄 Generated XML", "✅ Validation", "📈 Diagram"]
    )

    # Clear previous results and show waiting state
    with tab1:
        json_placeholder = st.empty()
        json_placeholder.info("⏳ Waiting for Stage 1...")

    with tab2:
        xml_placeholder = st.empty()
        xml_placeholder.info("⏳ Waiting for Stage 2...")

    with tab3:
        validation_placeholder = st.empty()
        validation_placeholder.info("⏳ Waiting for Stage 3...")

    with tab4:
        diagram_placeholder = st.empty()
        diagram_placeholder.info("⏳ Waiting for workflow data...")

    with col_progress:
        with st.status("🔄 Processing workflow...", expanded=True) as status:
            # Stage 1: Parse Intent
            st.write("🎯 **Stage 1:** Parsing natural language intent...")
            update_thinking("Analyzing workflow description...")

            state = PipelineState(
                user_input=user_input, output_format=output_format, max_repairs=max_repairs
            )

            try:
                state = run_with_timeout(
                    pipeline.parse_intent(state),
                    timeout=timeout_seconds,
                    stage_name="Intent Parsing",
                )
            except PipelineTimeout as e:
                state.error_message = str(e)
                st.error(f"⏱️ {e}")
                update_thinking(f"TIMEOUT: {e}", status="error")
                status.update(label="⏱️ Pipeline timed out", state="error")
            except Exception as e:
                state.error_message = str(e)
                logger.exception(f"Stage 1 exception: {e}")

            if state.error_message:
                st.error(f"❌ Intent parsing failed: {state.error_message}")
                update_thinking(f"ERROR: {state.error_message}", status="error")
                status.update(label="❌ Pipeline failed", state="error")
            else:
                st.success("✅ Intent parsed successfully")

                # Show AI reasoning if available
                if state.stage_thinking.get("intent"):
                    for line in state.stage_thinking["intent"].split(". "):
                        if line.strip():
                            update_thinking(line.strip() + "...")

                # UPDATE TAB 1 IMMEDIATELY
                with tab1:
                    json_placeholder.empty()
                    if state.workflow_json:
                        st.json(state.workflow_json.model_dump())
                    else:
                        st.warning("No workflow specification generated")

                # Stage 2: Generate XML
                st.write(f"📝 **Stage 2:** Generating {output_format.upper()} XML...")
                update_thinking(f"Converting to {output_format.upper()} format...")

                try:
                    state = run_with_timeout(
                        pipeline.generate_xml(state),
                        timeout=timeout_seconds,
                        stage_name="XML Generation",
                    )
                except PipelineTimeout as e:
                    state.error_message = str(e)
                    st.error(f"⏱️ {e}")
                    update_thinking(f"TIMEOUT: {e}", status="error")
                except Exception as e:
                    state.error_message = str(e)
                    logger.exception(f"Stage 2 exception: {e}")

                if state.error_message:
                    st.error(f"❌ XML generation failed: {state.error_message}")
                    update_thinking(f"ERROR: {state.error_message}", status="error")
                    status.update(label="❌ Pipeline failed", state="error")
                elif not state.draft_xml:
                    st.error("❌ XML generation returned empty result")
                    update_thinking("ERROR: No XML generated", status="error")
                    status.update(label="❌ Pipeline failed", state="error")
                else:
                    st.success("✅ XML generated")
                    update_thinking("XML structure created successfully")

                    # UPDATE TAB 2 IMMEDIATELY
                    with tab2:
                        xml_placeholder.empty()
                        st.code(pretty_print_xml(state.draft_xml), language="xml")
                        st.download_button(
                            label=f"📥 Download {output_format.upper()} File",
                            data=pretty_print_xml(state.draft_xml),
                            file_name=f"workflow.{output_format if output_format == 'bpmn' else 'bpel'}",
                            mime="application/xml",
                        )

                    # Stage 3: Validate (no timeout needed - deterministic)
                    st.write("✅ **Stage 3:** Validating XML...")
                    update_thinking("Running XSD schema validation...")
                    update_thinking("Checking semantic constraints...")

                    try:
                        state = run_with_timeout(
                            pipeline.validate_xml(state),
                            timeout=30,  # Validation is fast
                            stage_name="XML Validation",
                        )
                    except Exception as e:
                        state.error_message = str(e)
                        logger.exception(f"Stage 3 exception: {e}")

                    # UPDATE TAB 3 IMMEDIATELY
                    with tab3:
                        validation_placeholder.empty()
                        if state.validation_result:
                            if state.validation_result.valid:
                                st.success(
                                    "✅ **XML is valid!** All schema and semantic checks passed."
                                )
                                update_thinking("Validation passed!")
                            else:
                                st.error(
                                    f"**Found {len(state.validation_result.errors)} validation error(s):**"
                                )
                                for err in state.validation_result.errors:
                                    st.markdown(f"❌ **{err.message}**")
                                    if err.location:
                                        st.caption(f"Location: `{err.location}`")
                                    if err.suggestion:
                                        st.info(f"💡 {err.suggestion}")
                                update_thinking(
                                    f"Found {len(state.validation_result.errors)} errors"
                                )

                            if state.validation_result.warnings:
                                st.warning(
                                    f"**{len(state.validation_result.warnings)} warning(s):**"
                                )
                                for warn in state.validation_result.warnings:
                                    st.markdown(f"⚠️ {warn.message}")

                    if state.validation_result and state.validation_result.valid:
                        st.success("✅ Validation passed")
                    else:
                        st.warning(
                            f"⚠️ Validation found {len(state.validation_result.errors if state.validation_result else [])} errors"
                        )

                        # Stage 4: Repair loop
                        repair_count = 0
                        while state.validation_result and not state.validation_result.valid:
                            if state.repair_attempts >= max_repairs:
                                st.error(f"❌ Max repair attempts ({max_repairs}) reached")
                                update_thinking("Max repairs reached", status="error")
                                break

                            repair_count += 1
                            st.write(f"🔧 **Stage 4:** Repair attempt {repair_count}...")
                            update_thinking(f"Attempting repair #{repair_count}...")

                            try:
                                state = run_with_timeout(
                                    pipeline.repair_xml(state),
                                    timeout=timeout_seconds,
                                    stage_name=f"Repair Attempt {repair_count}",
                                )
                            except PipelineTimeout as e:
                                st.error(f"⏱️ Repair timed out: {e}")
                                update_thinking(f"TIMEOUT: {e}")
                                break
                            except Exception as e:
                                logger.exception(f"Stage 4 exception: {e}")
                                st.error(f"Repair failed: {e}")
                                break

                            # Update tabs after repair
                            with tab2:
                                xml_placeholder.empty()
                                xml_output = state.final_xml or state.draft_xml
                                if xml_output:
                                    st.code(pretty_print_xml(xml_output), language="xml")

                            with tab3:
                                validation_placeholder.empty()
                                if state.validation_result:
                                    if state.validation_result.valid:
                                        st.success("✅ **Repair successful!** XML is now valid.")
                                        update_thinking("Repair successful!")
                                    else:
                                        st.error(
                                            f"Still {len(state.validation_result.errors)} error(s)"
                                        )
                                        for err in state.validation_result.errors:
                                            st.markdown(f"❌ {err.message}")

                            if state.validation_result and state.validation_result.valid:
                                st.success("✅ Repair successful")

                    # Final status and diagram update
                    if state.validation_result and state.validation_result.valid:
                        status.update(label="✅ Pipeline completed successfully", state="complete")
                        update_thinking("Pipeline complete!", status="complete")
                        logger.info("Pipeline completed successfully")

                        # UPDATE TAB 4 (Diagram) only on successful completion
                        with tab4:
                            diagram_placeholder.empty()
                            if state.workflow_json:
                                render_workflow_diagram(state.workflow_json.workflow)
                    elif state.error_message:
                        status.update(label="❌ Pipeline failed", state="error")
                        update_thinking("Pipeline failed", status="error")
                        logger.error(f"Pipeline failed: {state.error_message}")
                    else:
                        status.update(label="⚠️ Pipeline completed with warnings", state="complete")
                        update_thinking("Completed with warnings", status="complete")
                        logger.warning("Pipeline completed with warnings")

                        # Show diagram even with warnings (XML was generated)
                        with tab4:
                            diagram_placeholder.empty()
                            if state.workflow_json:
                                render_workflow_diagram(state.workflow_json.workflow)

                    # Store final state in session for persistence
                    st.session_state.pipeline_state = state

elif generate_btn:
    st.warning("⚠️ Please enter a workflow description")

# Show previous results if available (when user clicks around without regenerating)
elif st.session_state.pipeline_state is not None:
    state = st.session_state.pipeline_state
    st.info("📋 Showing results from previous generation. Click 'Generate Workflow' to run again.")

    # Display stored results
    st.divider()
    st.subheader("📊 Previous Results")

    tab1, tab2, tab3, tab4 = st.tabs(
        ["📋 JSON Spec", "📄 Generated XML", "✅ Validation", "📈 Diagram"]
    )

    with tab1:
        if state.workflow_json:
            st.json(state.workflow_json.model_dump())
        else:
            st.warning("No workflow specification")

    with tab2:
        xml_output = state.final_xml or state.draft_xml
        if xml_output:
            st.code(pretty_print_xml(xml_output), language="xml")
        else:
            st.warning("No XML generated")

    with tab3:
        if state.validation_result:
            if state.validation_result.valid:
                st.success("✅ XML is valid")
            else:
                st.error(f"Found {len(state.validation_result.errors)} error(s)")
                for err in state.validation_result.errors:
                    st.markdown(f"❌ {err.message}")

    with tab4:
        if state.workflow_json:
            render_workflow_diagram(state.workflow_json.workflow)

# Footer
st.divider()
st.markdown(
    """
<div style='text-align: center; color: #666;'>
    <small>
        Built with Microsoft Agent Framework | Sequential Orchestration Pattern<br>
        <a href="https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/ai-agent-design-patterns">
            AI Agent Orchestration Patterns
        </a>
    </small>
</div>
""",
    unsafe_allow_html=True,
)
