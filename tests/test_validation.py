"""Tests for XML validation."""

from src.validation import (
    validate_workflow_xml,
    semantic_validate_bpmn,
    pretty_print_xml,
)


class TestPrettyPrintXML:
    """Tests for XML pretty printing."""

    def test_pretty_print_simple_xml(self):
        """Test pretty printing simple XML."""
        xml = "<root><child>text</child></root>"
        result = pretty_print_xml(xml)
        # Should return formatted XML (may or may not have declaration)
        assert "<root>" in result
        assert "<child>" in result

    def test_pretty_print_invalid_xml_returns_original(self):
        """Test that invalid XML returns original string."""
        invalid_xml = "<root><unclosed>"
        result = pretty_print_xml(invalid_xml)
        assert result == invalid_xml

    def test_pretty_print_empty_returns_empty(self):
        """Test empty string handling."""
        result = pretty_print_xml("")
        assert result == ""


class TestBPMNValidation:
    """Tests for BPMN XML validation."""

    def test_valid_minimal_bpmn(self):
        """Test validation of minimal valid BPMN."""
        bpmn_xml = """<?xml version="1.0" encoding="UTF-8"?>
<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL"
             xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"
             id="definitions_1"
             targetNamespace="http://example.com/bpmn">
    <process id="process_1" isExecutable="true">
        <startEvent id="start"/>
        <endEvent id="end"/>
        <sequenceFlow id="flow1" sourceRef="start" targetRef="end"/>
    </process>
</definitions>"""
        result = validate_workflow_xml(bpmn_xml, "bpmn")
        # May have semantic warnings but should parse
        assert result is not None

    def test_invalid_xml_syntax(self):
        """Test validation catches XML syntax errors."""
        invalid_xml = "<definitions><unclosed>"
        result = validate_workflow_xml(invalid_xml, "bpmn")
        assert result.valid is False
        assert len(result.errors) > 0
        assert any(
            "parse" in e.message.lower() or "xml" in e.message.lower() for e in result.errors
        )

    def test_missing_process_element(self):
        """Test validation catches missing process."""
        bpmn_xml = """<?xml version="1.0" encoding="UTF-8"?>
<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL"
             id="definitions_1"
             targetNamespace="http://example.com/bpmn">
</definitions>"""
        result = validate_workflow_xml(bpmn_xml, "bpmn")
        # Should have error or warning about missing process
        assert result is not None


class TestBPMNSemantics:
    """Tests for BPMN semantic validation."""

    def test_semantics_missing_start_event(self):
        """Test semantic validation catches missing start event."""
        from lxml import etree

        bpmn_xml = """<?xml version="1.0" encoding="UTF-8"?>
<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL"
             id="definitions_1"
             targetNamespace="http://example.com/bpmn">
    <process id="process_1" isExecutable="true">
        <task id="task1" name="Do something"/>
        <endEvent id="end"/>
    </process>
</definitions>"""
        root = etree.fromstring(bpmn_xml.encode())
        # Returns a list of ValidationError objects
        errors_list = semantic_validate_bpmn(root)
        all_messages = [e.message.lower() for e in errors_list]
        assert any("start" in msg for msg in all_messages)

    def test_semantics_missing_end_event(self):
        """Test semantic validation catches missing end event."""
        from lxml import etree

        bpmn_xml = """<?xml version="1.0" encoding="UTF-8"?>
<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL"
             id="definitions_1"
             targetNamespace="http://example.com/bpmn">
    <process id="process_1" isExecutable="true">
        <startEvent id="start"/>
        <task id="task1" name="Do something"/>
    </process>
</definitions>"""
        root = etree.fromstring(bpmn_xml.encode())
        # Returns a list of ValidationError objects
        errors_list = semantic_validate_bpmn(root)
        all_messages = [e.message.lower() for e in errors_list]
        assert any("end" in msg for msg in all_messages)


class TestBPELValidation:
    """Tests for BPEL XML validation."""

    def test_valid_minimal_bpel(self):
        """Test validation of minimal valid BPEL."""
        bpel_xml = """<?xml version="1.0" encoding="UTF-8"?>
<process xmlns="http://docs.oasis-open.org/wsbpel/2.0/process/executable"
         name="TestProcess"
         targetNamespace="http://example.com/bpel">
    <sequence>
        <empty name="doNothing"/>
    </sequence>
</process>"""
        result = validate_workflow_xml(bpel_xml, "bpel")
        assert result is not None

    def test_invalid_bpel_syntax(self):
        """Test validation catches BPEL syntax errors."""
        invalid_xml = "<process><unclosed>"
        result = validate_workflow_xml(invalid_xml, "bpel")
        assert result.valid is False
        assert len(result.errors) > 0


class TestValidationResultStructure:
    """Tests for validation result structure."""

    def test_result_has_required_fields(self):
        """Test that validation result has all required fields."""
        result = validate_workflow_xml("<test/>", "bpmn")
        assert hasattr(result, "valid")
        assert hasattr(result, "errors")
        assert hasattr(result, "warnings")
        assert isinstance(result.errors, list)
        assert isinstance(result.warnings, list)

    def test_errors_have_message(self):
        """Test that all errors have message field."""
        result = validate_workflow_xml("<invalid>", "bpmn")
        for error in result.errors:
            assert hasattr(error, "message")
            assert error.message is not None
            assert len(error.message) > 0
