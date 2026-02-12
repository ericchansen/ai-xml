"""Tests for the Streamlit application UI components.

These tests verify the app loads correctly and key components render.
Run with: uv run pytest tests/test_app.py -v
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestAppImports:
    """Test that app modules can be imported without errors."""

    def test_import_app_syntax(self):
        """Test that app.py has valid syntax."""
        app_path = Path(__file__).parent.parent / "app.py"
        assert app_path.exists()

        # Read with explicit encoding
        with open(app_path, encoding="utf-8") as f:
            code = f.read()

        # Compile to check for syntax errors
        compile(code, str(app_path), "exec")

    def test_import_pipeline(self):
        """Test that pipeline module imports correctly."""
        from src.pipeline import WorkflowPipeline, AzureOpenAIAgent

        assert WorkflowPipeline is not None
        assert AzureOpenAIAgent is not None

    def test_import_models(self):
        """Test that models module imports correctly."""
        from src.models import PipelineState, WorkflowSpec, Activity, SequenceFlow, Workflow

        assert PipelineState is not None
        assert WorkflowSpec is not None
        assert Activity is not None
        assert SequenceFlow is not None
        assert Workflow is not None

    def test_import_validation(self):
        """Test that validation module imports correctly."""
        from src.validation import (
            validate_workflow_xml,
            semantic_validate_bpmn,
            semantic_validate_bpel,
            pretty_print_xml,
        )

        assert validate_workflow_xml is not None
        assert semantic_validate_bpmn is not None
        assert semantic_validate_bpel is not None
        assert pretty_print_xml is not None

    def test_import_utils(self):
        """Test that utils module imports correctly."""
        from src.utils import run_with_timeout, PipelineTimeout, DEFAULT_TIMEOUT

        assert run_with_timeout is not None
        assert PipelineTimeout is not None
        assert DEFAULT_TIMEOUT == 60


class TestValidationFunctions:
    """Test XML validation functions."""

    def test_validate_valid_bpmn(self):
        """Test validation of valid BPMN XML."""
        from src.validation import validate_workflow_xml

        valid_bpmn = """<?xml version="1.0" encoding="UTF-8"?>
<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL"
             id="Definitions_1"
             targetNamespace="http://example.com/bpmn">
  <process id="Process_1" name="Test Process" isExecutable="true">
    <startEvent id="start"/>
    <endEvent id="end"/>
    <sequenceFlow id="flow1" sourceRef="start" targetRef="end"/>
  </process>
</definitions>"""

        result = validate_workflow_xml(valid_bpmn, "bpmn")

        assert result is not None

    def test_validate_invalid_xml_syntax(self):
        """Test validation catches XML syntax errors."""
        from src.validation import validate_workflow_xml

        invalid_xml = "<not-closed>"

        result = validate_workflow_xml(invalid_xml, "bpmn")

        # Should return result with errors, not crash
        assert result is not None
        assert not result.valid

    def test_pretty_print_xml(self):
        """Test XML pretty printing."""
        from src.validation import pretty_print_xml

        compact_xml = '<?xml version="1.0"?><root><child>text</child></root>'

        pretty = pretty_print_xml(compact_xml)

        assert pretty is not None
        assert "root" in pretty
        assert "child" in pretty


class TestTimeoutUtility:
    """Test the timeout wrapper utility."""

    def test_fast_function_completes(self):
        """Test that fast functions complete normally."""
        from src.utils import run_with_timeout

        async def fast_func():
            return "done"

        # run_with_timeout is sync (creates its own event loop)
        result = run_with_timeout(fast_func(), timeout=5)
        assert result == "done"

    def test_slow_function_times_out(self):
        """Test that slow functions raise timeout error."""
        import asyncio
        from src.utils import run_with_timeout, PipelineTimeout

        async def slow_func():
            await asyncio.sleep(10)
            return "done"

        with pytest.raises(PipelineTimeout):
            run_with_timeout(slow_func(), timeout=0.1)


class TestLoggingConfig:
    """Test logging configuration."""

    def test_get_logger(self):
        """Test getting a logger instance."""
        from src.logging_config import get_logger

        logger = get_logger("test")

        assert logger is not None
        assert hasattr(logger, "info")
        assert hasattr(logger, "error")

    def test_get_recent_logs(self):
        """Test retrieving recent log entries."""
        from src.logging_config import get_recent_logs

        # Should return a string (possibly "No logs yet." if empty)
        logs = get_recent_logs(10)

        assert isinstance(logs, str)


class TestExamplePrompts:
    """Test that example prompts are well-formed."""

    def test_example_prompts_exist(self):
        """Verify example prompts can be read from app."""
        app_path = Path(__file__).parent.parent / "pages" / "workflow.py"

        with open(app_path, encoding="utf-8") as f:
            content = f.read()

        # Check for expected example prompts
        assert "Order Processing" in content
        assert "Employee Onboarding" in content
        assert "Loan Approval" in content

    def test_example_prompts_are_multiline(self):
        """Verify example prompts have multiple steps."""
        app_path = Path(__file__).parent.parent / "pages" / "workflow.py"

        with open(app_path, encoding="utf-8") as f:
            content = f.read()

        # Examples should have numbered steps
        assert "1." in content
        assert "2." in content
        assert "3." in content
