"""Tests for Pydantic models."""

from src.models import (
    PipelineState,
    WorkflowSpec,
    Workflow,
    Activity,
    SequenceFlow,
    ActivityType,
    ValidationResult,
    ValidationError,
)


class TestPipelineState:
    """Tests for PipelineState model."""

    def test_default_state(self):
        """Test default pipeline state initialization."""
        state = PipelineState(user_input="Test workflow", output_format="bpmn")
        assert state.user_input == "Test workflow"
        assert state.output_format == "bpmn"
        assert state.workflow_json is None
        assert state.draft_xml is None
        assert state.final_xml is None
        assert state.validation_result is None
        assert state.error_message is None
        assert state.repair_attempts == 0
        assert state.max_repairs == 3
        assert state.stage_thinking == {}

    def test_state_with_custom_max_repairs(self):
        """Test state with custom max repairs."""
        state = PipelineState(user_input="Test", output_format="bpel", max_repairs=5)
        assert state.max_repairs == 5
        assert state.output_format == "bpel"

    def test_state_tracking_thinking(self):
        """Test that stage thinking can be tracked."""
        state = PipelineState(user_input="Test", output_format="bpmn")
        state.stage_thinking["intent"] = "Analyzing workflow structure..."
        state.stage_thinking["generate"] = "Creating BPMN elements..."

        assert len(state.stage_thinking) == 2
        assert "intent" in state.stage_thinking


class TestWorkflowModels:
    """Tests for workflow-related models."""

    def test_activity_creation(self):
        """Test Activity model creation."""
        activity = Activity(
            id="task_1",
            name="Process Order",
            type=ActivityType.TASK,
        )
        assert activity.id == "task_1"
        assert activity.name == "Process Order"
        assert activity.type == ActivityType.TASK

    def test_sequence_flow_creation(self):
        """Test SequenceFlow model creation."""
        flow = SequenceFlow(id="flow_1", source="start", target="task_1", name="Start to Task")
        assert flow.id == "flow_1"
        assert flow.source == "start"
        assert flow.target == "task_1"
        assert flow.condition is None

    def test_sequence_flow_with_condition(self):
        """Test SequenceFlow with gateway condition."""
        flow = SequenceFlow(
            id="flow_2",
            source="gateway_1",
            target="task_approved",
            name="Approved Path",
            condition="approved == true",
        )
        assert flow.condition == "approved == true"

    def test_workflow_creation(self):
        """Test Workflow model creation."""
        workflow = Workflow(
            name="Order Processing",
            activities=[
                Activity(id="start", name="Start", type=ActivityType.START_EVENT),
                Activity(id="task1", name="Process", type=ActivityType.TASK),
                Activity(id="end", name="End", type=ActivityType.END_EVENT),
            ],
            flows=[
                SequenceFlow(id="f1", source="start", target="task1"),
                SequenceFlow(id="f2", source="task1", target="end"),
            ],
        )
        assert workflow.name == "Order Processing"
        assert len(workflow.activities) == 3
        assert len(workflow.flows) == 2

    def test_workflow_spec_creation(self):
        """Test WorkflowSpec model wraps workflow."""
        spec = WorkflowSpec(workflow=Workflow(name="Test Workflow", activities=[], flows=[]))
        assert spec.workflow.name == "Test Workflow"


class TestValidationModels:
    """Tests for validation-related models."""

    def test_validation_error_creation(self):
        """Test ValidationError model."""
        error = ValidationError(
            severity="error",
            message="Missing required element",
            location="/definitions/process",
            suggestion="Add a process element to the definitions",
        )
        assert error.message == "Missing required element"
        assert error.location == "/definitions/process"
        assert error.suggestion is not None

    def test_validation_result_valid(self):
        """Test ValidationResult for valid XML."""
        result = ValidationResult(valid=True, errors=[], warnings=[])
        assert result.valid is True
        assert len(result.errors) == 0

    def test_validation_result_invalid(self):
        """Test ValidationResult for invalid XML."""
        result = ValidationResult(
            valid=False,
            errors=[
                ValidationError(severity="error", message="Error 1"),
                ValidationError(severity="error", message="Error 2"),
            ],
            warnings=[
                ValidationError(severity="warning", message="Warning 1"),
            ],
        )
        assert result.valid is False
        assert len(result.errors) == 2
        assert len(result.warnings) == 1


class TestActivityTypes:
    """Tests for ActivityType enum."""

    def test_core_activity_types_exist(self):
        """Test that core activity types exist."""
        expected_types = [
            "startEvent",
            "endEvent",
            "task",
            "serviceTask",
            "userTask",
            "scriptTask",
            "exclusiveGateway",
            "parallelGateway",
        ]
        actual_types = [t.value for t in ActivityType]
        for expected in expected_types:
            assert expected in actual_types, f"Missing activity type: {expected}"
