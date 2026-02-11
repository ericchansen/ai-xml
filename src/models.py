"""Pydantic models for intermediate workflow representation."""

from enum import Enum
from typing import Optional
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
    """A workflow activity (task, event, or gateway)."""

    id: str = Field(..., description="Unique identifier for the activity")
    type: ActivityType = Field(..., description="Type of activity")
    name: Optional[str] = Field(None, description="Human-readable name")
    operation: Optional[str] = Field(None, description="Operation/service to invoke")
    implementation: Optional[str] = Field(None, description="Implementation reference")
    assignee: Optional[str] = Field(None, description="User/role for user tasks")
    script: Optional[str] = Field(None, description="Script content for script tasks")
    condition: Optional[str] = Field(
        None, description="Condition expression for gateways/conditionals"
    )


class SequenceFlow(BaseModel):
    """A flow connecting two activities."""

    model_config = {"populate_by_name": True}

    id: Optional[str] = Field(None, description="Unique flow identifier")
    source: str = Field(..., alias="from", description="Source activity ID")
    target: str = Field(..., alias="to", description="Target activity ID")
    name: Optional[str] = Field(None, description="Flow label (e.g., 'Yes', 'No')")
    condition: Optional[str] = Field(None, description="Condition expression for conditional flows")


class Variable(BaseModel):
    """A process variable."""

    name: str = Field(..., description="Variable name")
    type: Optional[str] = Field(
        None, description="Variable type (e.g., 'string', 'integer', 'messageType')"
    )
    description: Optional[str] = Field(None, description="Variable description")


class PartnerLink(BaseModel):
    """A BPEL partner link (external service relationship)."""

    name: str = Field(..., description="Partner link name")
    partner_link_type: str = Field(..., description="Partner link type reference")
    my_role: Optional[str] = Field(None, description="Role this process plays")
    partner_role: Optional[str] = Field(None, description="Role the partner plays")


class Workflow(BaseModel):
    """Intermediate workflow representation (JSON schema for LLM generation)."""

    name: str = Field(..., description="Workflow/process name")
    description: Optional[str] = Field(None, description="Human-readable description")
    namespace: str = Field(
        default="http://example.com/workflow", description="Target namespace URI"
    )
    activities: list[Activity] = Field(
        default_factory=list, description="List of activities in the workflow"
    )
    flows: list[SequenceFlow] = Field(
        default_factory=list, description="Sequence flows connecting activities"
    )
    variables: list[Variable] = Field(default_factory=list, description="Process variables")
    partner_links: list[PartnerLink] = Field(
        default_factory=list, description="BPEL partner links (for external services)"
    )


class WorkflowSpec(BaseModel):
    """Top-level container for workflow specification."""

    workflow: Workflow


# JSON Schema for LLM prompts
WORKFLOW_JSON_SCHEMA = WorkflowSpec.model_json_schema()


class ValidationError(BaseModel):
    """A validation error found in the workflow."""

    severity: str = Field(..., description="'error' or 'warning'")
    message: str = Field(..., description="Error description")
    location: Optional[str] = Field(None, description="XPath or activity ID where error occurred")
    suggestion: Optional[str] = Field(None, description="Suggested fix")


class ValidationResult(BaseModel):
    """Result of workflow validation."""

    valid: bool = Field(..., description="Whether the workflow is valid")
    errors: list[ValidationError] = Field(default_factory=list)
    warnings: list[ValidationError] = Field(default_factory=list)
    xml_output: Optional[str] = Field(None, description="Generated XML if valid")


class PipelineState(BaseModel):
    """State passed through the sequential agent pipeline."""

    user_input: str = Field(..., description="Original natural language input")
    workflow_json: Optional[WorkflowSpec] = Field(None, description="Parsed workflow spec")
    draft_xml: Optional[str] = Field(None, description="Draft BPMN/BPEL XML")
    validation_result: Optional[ValidationResult] = Field(None, description="Validation result")
    final_xml: Optional[str] = Field(None, description="Final validated XML")
    output_format: str = Field(default="bpmn", description="'bpmn' or 'bpel'")
    repair_attempts: int = Field(default=0, description="Number of repair iterations")
    max_repairs: int = Field(default=3, description="Maximum repair attempts")
    error_message: Optional[str] = Field(None, description="Error if pipeline failed")
    stage_thinking: dict[str, str] = Field(
        default_factory=dict, description="LLM reasoning for each stage"
    )
