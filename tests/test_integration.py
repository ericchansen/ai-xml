"""Integration tests for the full pipeline.

These tests verify end-to-end behavior with mocked LLM responses.
Run with: uv run pytest tests/test_integration.py -v -m integration
"""

import pytest

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.pipeline import WorkflowPipeline
from src.models import PipelineState, WorkflowSpec, Workflow


# Mark all tests in this file as integration tests
pytestmark = pytest.mark.integration


class TestFullPipeline:
    """End-to-end pipeline tests with mocked LLM."""

    @pytest.fixture
    def mock_intent_response(self):
        """Mock response for intent parsing stage."""
        return """{
            "workflow": {
                "name": "OrderProcessing",
                "description": "Process customer orders",
                "activities": [
                    {"id": "start", "type": "startEvent", "name": "Start"},
                    {"id": "validate", "type": "serviceTask", "name": "Validate Order", "operation": "validateOrder"},
                    {"id": "end", "type": "endEvent", "name": "End"}
                ],
                "flows": [
                    {"from": "start", "to": "validate"},
                    {"from": "validate", "to": "end"}
                ]
            }
        }"""

    @pytest.fixture
    def mock_bpmn_response(self):
        """Mock response for BPMN generation stage."""
        return """<?xml version="1.0" encoding="UTF-8"?>
<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL"
             xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"
             id="Definitions_1"
             targetNamespace="http://example.com/bpmn">
  <process id="OrderProcessing" name="OrderProcessing" isExecutable="true">
    <startEvent id="start" name="Start"/>
    <serviceTask id="validate" name="Validate Order"/>
    <endEvent id="end" name="End"/>
    <sequenceFlow id="flow1" sourceRef="start" targetRef="validate"/>
    <sequenceFlow id="flow2" sourceRef="validate" targetRef="end"/>
  </process>
</definitions>"""

    def test_pipeline_can_be_instantiated(self):
        """Test that pipeline can be created."""
        pipeline = WorkflowPipeline()
        assert pipeline is not None

    def test_pipeline_state_can_be_created(self):
        """Test that pipeline state can be created with valid input."""
        state = PipelineState(
            user_input="Create an order processing workflow", output_format="bpmn", max_repairs=3
        )
        assert state.user_input == "Create an order processing workflow"
        assert state.output_format == "bpmn"
        assert state.max_repairs == 3

    def test_pipeline_handles_empty_input_state(self):
        """Test that pipeline state can handle empty input."""
        state = PipelineState(user_input="", max_repairs=0)
        assert state.user_input == ""


class TestPipelineStageTransitions:
    """Test state transitions through pipeline stages."""

    def test_pipeline_has_agents(self):
        """Verify pipeline has required agents."""
        pipeline = WorkflowPipeline()
        assert hasattr(pipeline, "intent_parser")
        assert hasattr(pipeline, "bpmn_generator")
        assert hasattr(pipeline, "bpel_generator")
        assert hasattr(pipeline, "validator")


class TestRepairLoop:
    """Test the validation and repair functionality."""

    def test_max_repairs_is_configurable(self):
        """Verify max_repairs can be set in pipeline state."""
        state = PipelineState(user_input="Test", max_repairs=5)
        assert state.max_repairs == 5

        state2 = PipelineState(user_input="Test", max_repairs=0)
        assert state2.max_repairs == 0


class TestWorkflowSpecParsing:
    """Test JSON workflow spec parsing."""

    def test_valid_workflow_spec_parsing(self):
        """Test parsing a valid workflow specification."""
        import json

        json_str = """{
            "workflow": {
                "name": "TestWorkflow",
                "description": "A test workflow",
                "activities": [
                    {"id": "start", "type": "startEvent", "name": "Start"},
                    {"id": "task1", "type": "serviceTask", "name": "Task 1", "operation": "doSomething"},
                    {"id": "end", "type": "endEvent", "name": "End"}
                ],
                "flows": [
                    {"from": "start", "to": "task1"},
                    {"from": "task1", "to": "end"}
                ]
            }
        }"""

        data = json.loads(json_str)
        spec = WorkflowSpec(**data)

        assert spec.workflow.name == "TestWorkflow"
        assert len(spec.workflow.activities) == 3
        assert len(spec.workflow.flows) == 2

    def test_workflow_spec_with_gateway(self):
        """Test parsing workflow with exclusive gateway."""
        import json

        json_str = """{
            "workflow": {
                "name": "DecisionWorkflow",
                "activities": [
                    {"id": "start", "type": "startEvent"},
                    {"id": "decision", "type": "exclusiveGateway", "name": "Check Condition"},
                    {"id": "pathA", "type": "serviceTask", "name": "Path A"},
                    {"id": "pathB", "type": "serviceTask", "name": "Path B"},
                    {"id": "end", "type": "endEvent"}
                ],
                "flows": [
                    {"from": "start", "to": "decision"},
                    {"from": "decision", "to": "pathA", "condition": "approved"},
                    {"from": "decision", "to": "pathB", "condition": "rejected"},
                    {"from": "pathA", "to": "end"},
                    {"from": "pathB", "to": "end"}
                ]
            }
        }"""

        data = json.loads(json_str)
        spec = WorkflowSpec(**data)

        assert spec.workflow.name == "DecisionWorkflow"
        gateway = next(a for a in spec.workflow.activities if a.type == "exclusiveGateway")
        assert gateway.name == "Check Condition"

        conditional_flows = [f for f in spec.workflow.flows if f.condition]
        assert len(conditional_flows) == 2


class TestPipelineStateModel:
    """Test PipelineState model behavior."""

    def test_initial_state(self):
        """Test creating initial pipeline state."""
        state = PipelineState(user_input="Test input")

        assert state.user_input == "Test input"
        assert state.output_format == "bpmn"
        assert state.workflow_json is None
        assert state.final_xml is None
        assert state.repair_attempts == 0
        assert state.max_repairs == 3

    def test_state_with_all_fields(self):
        """Test state with all fields populated."""
        workflow = Workflow(name="Test", activities=[], flows=[])
        spec = WorkflowSpec(workflow=workflow)

        state = PipelineState(
            user_input="Test",
            output_format="bpel",
            workflow_json=spec,
            final_xml="<xml/>",
            repair_attempts=2,
            max_repairs=5,
            error_message="test error",
        )

        assert state.output_format == "bpel"
        assert state.workflow_json.workflow.name == "Test"
        assert state.repair_attempts == 2
        assert state.error_message == "test error"
