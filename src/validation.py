"""XML validation utilities using lxml."""

from pathlib import Path
from typing import Optional
from lxml import etree

from .models import ValidationError, ValidationResult


SCHEMAS_DIR = Path(__file__).parent.parent / "schemas"

# Namespace URIs
BPMN_NS = "http://www.omg.org/spec/BPMN/20100524/MODEL"
BPEL_NS = "http://docs.oasis-open.org/wsbpel/2.0/process/executable"


def load_xsd_schema(schema_path: Path) -> Optional[etree.XMLSchema]:
    """Load an XSD schema from file."""
    try:
        with open(schema_path, "rb") as f:
            schema_doc = etree.parse(f)
            return etree.XMLSchema(schema_doc)
    except Exception as e:
        print(f"Warning: Could not load schema {schema_path}: {e}")
        return None


def validate_xml_syntax(xml_string: str) -> tuple[bool, Optional[str], Optional[etree._Element]]:
    """Check if XML is well-formed. Returns (valid, error_message, parsed_tree)."""
    try:
        tree = etree.fromstring(xml_string.encode("utf-8"))
        return True, None, tree
    except etree.XMLSyntaxError as e:
        return False, str(e), None


def validate_against_xsd(
    xml_tree: etree._Element, schema: etree.XMLSchema
) -> list[ValidationError]:
    """Validate XML against XSD schema."""
    errors = []
    try:
        schema.assertValid(xml_tree)
    except etree.DocumentInvalid:
        for error in schema.error_log:
            errors.append(
                ValidationError(
                    severity="error",
                    message=error.message,
                    location=f"Line {error.line}",
                    suggestion="Check the element structure against the schema",
                )
            )
    return errors


def semantic_validate_bpmn(xml_tree: etree._Element) -> list[ValidationError]:
    """Perform semantic validation on BPMN XML."""
    errors = []
    warnings = []

    nsmap = {"bpmn": BPMN_NS}

    # Find all processes
    processes = xml_tree.xpath("//bpmn:process", namespaces=nsmap)
    if not processes:
        # Try without namespace for simplified XMLs
        processes = xml_tree.xpath("//*[local-name()='process']")

    for process in processes:
        process_id = process.get("id", "unknown")

        # Check for start events
        start_events = process.xpath(".//*[local-name()='startEvent']")
        if not start_events:
            errors.append(
                ValidationError(
                    severity="error",
                    message=f"Process '{process_id}' has no startEvent",
                    location=f"process[@id='{process_id}']",
                    suggestion="Add a <startEvent> element",
                )
            )
        elif len(start_events) > 1:
            warnings.append(
                ValidationError(
                    severity="warning",
                    message=f"Process '{process_id}' has multiple startEvents",
                    location=f"process[@id='{process_id}']",
                    suggestion="Consider if multiple start events are intentional",
                )
            )

        # Check for end events
        end_events = process.xpath(".//*[local-name()='endEvent']")
        if not end_events:
            errors.append(
                ValidationError(
                    severity="error",
                    message=f"Process '{process_id}' has no endEvent",
                    location=f"process[@id='{process_id}']",
                    suggestion="Add an <endEvent> element",
                )
            )

        # Collect all activity IDs
        activities = process.xpath(
            ".//*[local-name()='startEvent' or local-name()='endEvent' or "
            "local-name()='task' or local-name()='serviceTask' or "
            "local-name()='userTask' or local-name()='scriptTask' or "
            "local-name()='exclusiveGateway' or local-name()='parallelGateway']"
        )
        activity_ids = {a.get("id") for a in activities if a.get("id")}

        # Check sequence flows
        flows = process.xpath(".//*[local-name()='sequenceFlow']")
        for flow in flows:
            flow_id = flow.get("id", "unknown")
            source_ref = flow.get("sourceRef")
            target_ref = flow.get("targetRef")

            if source_ref and source_ref not in activity_ids:
                errors.append(
                    ValidationError(
                        severity="error",
                        message=f"Flow '{flow_id}' references non-existent source '{source_ref}'",
                        location=f"sequenceFlow[@id='{flow_id}']",
                        suggestion=f"Ensure activity with id='{source_ref}' exists",
                    )
                )

            if target_ref and target_ref not in activity_ids:
                errors.append(
                    ValidationError(
                        severity="error",
                        message=f"Flow '{flow_id}' references non-existent target '{target_ref}'",
                        location=f"sequenceFlow[@id='{flow_id}']",
                        suggestion=f"Ensure activity with id='{target_ref}' exists",
                    )
                )

        # Check for unreachable activities (simple check)
        sources = {f.get("sourceRef") for f in flows}
        targets = {f.get("targetRef") for f in flows}
        start_ids = {s.get("id") for s in start_events}
        end_ids = {e.get("id") for e in end_events}

        for act_id in activity_ids:
            if act_id not in start_ids and act_id not in targets:
                warnings.append(
                    ValidationError(
                        severity="warning",
                        message=f"Activity '{act_id}' may be unreachable (no incoming flows)",
                        location=f"*[@id='{act_id}']",
                        suggestion="Add a sequence flow targeting this activity",
                    )
                )
            if act_id not in end_ids and act_id not in sources:
                warnings.append(
                    ValidationError(
                        severity="warning",
                        message=f"Activity '{act_id}' may be a dead end (no outgoing flows)",
                        location=f"*[@id='{act_id}']",
                        suggestion="Add a sequence flow from this activity",
                    )
                )

    return errors + warnings


def semantic_validate_bpel(xml_tree: etree._Element) -> list[ValidationError]:
    """Perform semantic validation on BPEL XML."""
    errors = []
    warnings = []

    # Check root element
    root_tag = etree.QName(xml_tree.tag).localname
    if root_tag != "process":
        errors.append(
            ValidationError(
                severity="error",
                message=f"Root element should be 'process', found '{root_tag}'",
                location="/",
                suggestion="Change root element to <process>",
            )
        )
        return errors

    # Check required attributes
    if not xml_tree.get("name"):
        errors.append(
            ValidationError(
                severity="error",
                message="Process missing required 'name' attribute",
                location="/process",
                suggestion="Add name attribute to process element",
            )
        )

    if not xml_tree.get("targetNamespace"):
        errors.append(
            ValidationError(
                severity="error",
                message="Process missing required 'targetNamespace' attribute",
                location="/process",
                suggestion="Add targetNamespace attribute to process element",
            )
        )

    # Check for at least one activity
    activities = xml_tree.xpath(
        ".//*[local-name()='receive' or local-name()='reply' or "
        "local-name()='invoke' or local-name()='assign' or "
        "local-name()='sequence' or local-name()='if' or "
        "local-name()='while' or local-name()='flow']"
    )
    if not activities:
        errors.append(
            ValidationError(
                severity="error",
                message="Process has no activities",
                location="/process",
                suggestion="Add at least one activity (receive, invoke, etc.)",
            )
        )

    # Check for receive with createInstance (entry point)
    receives = xml_tree.xpath(".//*[local-name()='receive']")
    has_entry = any(r.get("createInstance") == "true" for r in receives)
    if receives and not has_entry:
        warnings.append(
            ValidationError(
                severity="warning",
                message="No receive activity with createInstance='true' found",
                location="/process",
                suggestion="Mark the initial receive with createInstance='true'",
            )
        )

    return errors + warnings


def validate_workflow_xml(xml_string: str, output_format: str = "bpmn") -> ValidationResult:
    """Full validation of workflow XML."""
    errors = []
    warnings = []

    # Step 1: Syntax check
    is_valid, syntax_error, xml_tree = validate_xml_syntax(xml_string)
    if not is_valid:
        return ValidationResult(
            valid=False,
            errors=[
                ValidationError(
                    severity="error",
                    message=f"XML syntax error: {syntax_error}",
                    location="document",
                    suggestion="Fix the XML syntax",
                )
            ],
        )

    # Step 2: XSD validation (optional, may not have full schema)
    if output_format == "bpmn":
        semantic_errors = semantic_validate_bpmn(xml_tree)
    else:
        semantic_errors = semantic_validate_bpel(xml_tree)

    # Separate errors and warnings
    for err in semantic_errors:
        if err.severity == "error":
            errors.append(err)
        else:
            warnings.append(err)

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        xml_output=xml_string if len(errors) == 0 else None,
    )


def pretty_print_xml(xml_string: str) -> str:
    """Format XML with proper indentation."""
    try:
        tree = etree.fromstring(xml_string.encode("utf-8"))
        return etree.tostring(tree, pretty_print=True, encoding="unicode", xml_declaration=True)
    except Exception:
        return xml_string
