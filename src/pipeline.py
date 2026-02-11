"""Sequential agent pipeline using Microsoft Agent Framework."""

import asyncio
import json
import os
import time

from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

from .models import (
    PipelineState,
    WorkflowSpec,
    WORKFLOW_JSON_SCHEMA,
)
from .prompts import (
    INTENT_PARSER_SYSTEM,
    SCHEMA_GENERATOR_BPMN_SYSTEM,
    SCHEMA_GENERATOR_BPEL_SYSTEM,
    VALIDATOR_SYSTEM,
    REPAIR_SYSTEM,
)
from .validation import validate_workflow_xml, pretty_print_xml
from .logging_config import get_logger

load_dotenv()

# Get logger for this module
logger = get_logger("ai_workflow.pipeline")


# Try to import OpenAI for Azure OpenAI
try:
    from openai import AzureOpenAI

    AZURE_OPENAI_AVAILABLE = True
except ImportError:
    AZURE_OPENAI_AVAILABLE = False

# Try to import Agent Framework components
try:
    from agent_framework import ChatAgent  # noqa: F401

    AGENT_FRAMEWORK_AVAILABLE = True
except ImportError:
    AGENT_FRAMEWORK_AVAILABLE = False

# Try to import GitHub Copilot agent
try:
    from agent_framework.github import GitHubCopilotAgent

    GITHUB_COPILOT_AVAILABLE = True
except ImportError:
    GITHUB_COPILOT_AVAILABLE = False


class MockAgent:
    """Mock agent for testing when Agent Framework is not configured."""

    def __init__(self, name: str, instructions: str):
        self.name = name
        self.instructions = instructions

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def run(self, prompt: str) -> str:
        """Return mock responses for demo purposes."""
        if "intent" in self.name.lower() or "parser" in self.name.lower():
            # Mock intent parser response
            return json.dumps(
                {
                    "workflow": {
                        "name": "MockWorkflow",
                        "description": "Generated from user input",
                        "namespace": "http://example.com/mock",
                        "activities": [
                            {"id": "start", "type": "startEvent", "name": "Start"},
                            {
                                "id": "task1",
                                "type": "serviceTask",
                                "name": "Process",
                                "operation": "process",
                            },
                            {"id": "end", "type": "endEvent", "name": "End"},
                        ],
                        "flows": [{"from": "start", "to": "task1"}, {"from": "task1", "to": "end"}],
                        "variables": [],
                        "partner_links": [],
                    }
                }
            )
        elif "bpmn" in self.name.lower() or "generator" in self.name.lower():
            # Mock BPMN generator
            return """<?xml version="1.0" encoding="UTF-8"?>
<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL"
             id="MockDefinitions" targetNamespace="http://example.com/mock">
  <process id="MockProcess" name="Mock Process" isExecutable="true">
    <startEvent id="start" name="Start">
      <outgoing>flow1</outgoing>
    </startEvent>
    <serviceTask id="task1" name="Process">
      <incoming>flow1</incoming>
      <outgoing>flow2</outgoing>
    </serviceTask>
    <endEvent id="end" name="End">
      <incoming>flow2</incoming>
    </endEvent>
    <sequenceFlow id="flow1" sourceRef="start" targetRef="task1"/>
    <sequenceFlow id="flow2" sourceRef="task1" targetRef="end"/>
  </process>
</definitions>"""
        elif "validator" in self.name.lower():
            return json.dumps({"valid": True, "errors": [], "warnings": []})
        else:
            return "Mock response"


class AzureOpenAIAgent:
    """Agent using Azure OpenAI directly via the openai SDK."""

    def __init__(self, name: str, instructions: str):
        self.name = name
        self.instructions = instructions
        self._client = None

    async def __aenter__(self):
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        if not endpoint:
            raise ValueError("AZURE_OPENAI_ENDPOINT not set")

        token_provider = get_bearer_token_provider(
            DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
        )
        self._client = AzureOpenAI(
            azure_endpoint=endpoint,
            azure_ad_token_provider=token_provider,
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview"),
        )
        return self

    async def __aexit__(self, *args):
        self._client = None

    async def run(self, prompt: str) -> str:
        """Run a completion with the Azure OpenAI model."""
        deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o-mini")

        # Run in executor since openai SDK is sync
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self._client.chat.completions.create(
                model=deployment,
                messages=[
                    {"role": "system", "content": self.instructions},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=4000,
            ),
        )
        return response.choices[0].message.content


def create_agent(name: str, instructions: str, use_github_copilot: bool = False):
    """Factory to create appropriate agent based on available backends."""

    if use_github_copilot and GITHUB_COPILOT_AVAILABLE:
        return GitHubCopilotAgent(default_options={"instructions": instructions})

    # Use Azure OpenAI if configured
    if AZURE_OPENAI_AVAILABLE and os.getenv("AZURE_OPENAI_ENDPOINT"):
        return AzureOpenAIAgent(name=name, instructions=instructions)

    # Fall back to mock agent
    print("Warning: No LLM backend configured. Using mock agents.")
    return MockAgent(name=name, instructions=instructions)


class WorkflowPipeline:
    """Sequential orchestration pipeline for workflow generation."""

    def __init__(self, use_github_copilot: bool = False):
        self.use_github_copilot = use_github_copilot

        # Create agents with their specific instructions
        schema_json = json.dumps(WORKFLOW_JSON_SCHEMA, indent=2)

        self.intent_parser = create_agent(
            "IntentParser", INTENT_PARSER_SYSTEM.format(schema=schema_json), use_github_copilot
        )

        self.bpmn_generator = create_agent(
            "BPMNGenerator", SCHEMA_GENERATOR_BPMN_SYSTEM, use_github_copilot
        )

        self.bpel_generator = create_agent(
            "BPELGenerator", SCHEMA_GENERATOR_BPEL_SYSTEM, use_github_copilot
        )

        self.validator = create_agent("Validator", VALIDATOR_SYSTEM, use_github_copilot)

        self.repair_agent = create_agent("RepairAgent", REPAIR_SYSTEM, use_github_copilot)

    async def parse_intent(self, state: PipelineState) -> PipelineState:
        """Stage 1: Parse natural language to structured JSON."""
        start_time = time.time()
        logger.info("Stage 1: Starting intent parsing")
        logger.debug(f"Input: {state.user_input[:100]}...")

        try:
            async with self.intent_parser as agent:
                response = await agent.run(
                    f"Convert this workflow description to JSON:\n\n{state.user_input}"
                )

                # Parse the JSON response
                try:
                    # Clean up response (remove markdown if present)
                    json_str = response.strip()
                    if json_str.startswith("```"):
                        json_str = json_str.split("```")[1]
                        if json_str.startswith("json"):
                            json_str = json_str[4:]

                    workflow_data = json.loads(json_str)

                    # Extract thinking if present in response
                    if "thinking" in workflow_data:
                        state.stage_thinking["intent"] = workflow_data["thinking"]
                        # Remove thinking from the data before validation
                        workflow_data_clean = {
                            "workflow": workflow_data.get("workflow", workflow_data)
                        }
                        state.workflow_json = WorkflowSpec.model_validate(workflow_data_clean)
                    else:
                        state.workflow_json = WorkflowSpec.model_validate(workflow_data)

                    logger.info(
                        f"Stage 1: Parsed workflow '{state.workflow_json.workflow.name}' with {len(state.workflow_json.workflow.activities)} activities"
                    )
                except Exception as e:
                    state.error_message = f"Failed to parse intent: {e}"
                    logger.error(f"Stage 1: Parse error - {e}")
        except Exception as e:
            state.error_message = f"Stage 1 failed: {e}"
            logger.exception(f"Stage 1: Exception - {e}")

        elapsed = time.time() - start_time
        logger.info(f"Stage 1: Completed in {elapsed:.2f}s")
        return state

    async def generate_xml(self, state: PipelineState) -> PipelineState:
        """Stage 2: Generate XML from JSON spec."""
        if state.error_message or not state.workflow_json:
            logger.warning("Stage 2: Skipped due to previous error or missing workflow")
            return state

        start_time = time.time()
        logger.info(f"Stage 2: Starting {state.output_format.upper()} generation")

        try:
            generator = (
                self.bpmn_generator if state.output_format == "bpmn" else self.bpel_generator
            )

            async with generator as agent:
                workflow_json = state.workflow_json.model_dump_json(indent=2)
                response = await agent.run(
                    f"Generate {state.output_format.upper()} XML for this workflow:\n\n{workflow_json}"
                )

                # Clean up response
                xml_str = response.strip()
                if xml_str.startswith("```"):
                    xml_str = xml_str.split("```")[1]
                    if xml_str.startswith("xml"):
                        xml_str = xml_str[3:]
                    xml_str = xml_str.strip()

                state.draft_xml = xml_str
                logger.info(f"Stage 2: Generated {len(xml_str)} chars of XML")
        except Exception as e:
            state.error_message = f"Stage 2 failed: {e}"
            logger.exception(f"Stage 2: Exception - {e}")

        elapsed = time.time() - start_time
        logger.info(f"Stage 2: Completed in {elapsed:.2f}s")
        return state

    async def validate_xml(self, state: PipelineState) -> PipelineState:
        """Stage 3: Validate the generated XML."""
        if state.error_message or not state.draft_xml:
            logger.warning("Stage 3: Skipped due to previous error or missing XML")
            return state

        start_time = time.time()
        logger.info("Stage 3: Starting XML validation")

        try:
            # Use deterministic validation
            result = validate_workflow_xml(state.draft_xml, state.output_format)
            state.validation_result = result

            if result.valid:
                state.final_xml = pretty_print_xml(state.draft_xml)
                logger.info("Stage 3: Validation passed")
            else:
                logger.warning(f"Stage 3: Validation failed with {len(result.errors)} errors")
                for err in result.errors[:3]:
                    logger.warning(f"  - {err.message}")
        except Exception as e:
            state.error_message = f"Stage 3 failed: {e}"
            logger.exception(f"Stage 3: Exception - {e}")

        elapsed = time.time() - start_time
        logger.info(f"Stage 3: Completed in {elapsed:.2f}s")
        return state

    async def repair_xml(self, state: PipelineState) -> PipelineState:
        """Stage 4: Attempt to repair invalid XML."""
        if state.error_message:
            logger.warning("Stage 4: Skipped due to previous error")
            return state

        if not state.validation_result or state.validation_result.valid:
            logger.info("Stage 4: No repair needed")
            return state

        if state.repair_attempts >= state.max_repairs:
            state.error_message = f"Failed to repair XML after {state.max_repairs} attempts"
            logger.error(f"Stage 4: Max repair attempts ({state.max_repairs}) reached")
            return state

        state.repair_attempts += 1
        start_time = time.time()
        logger.info(f"Stage 4: Starting repair attempt {state.repair_attempts}/{state.max_repairs}")

        try:
            async with self.repair_agent as agent:
                errors_json = json.dumps(
                    [e.model_dump() for e in state.validation_result.errors], indent=2
                )
                workflow_json = (
                    state.workflow_json.model_dump_json(indent=2) if state.workflow_json else "{}"
                )

                prompt = f"""Fix this {state.output_format.upper()} XML that has validation errors.

Original workflow spec:
{workflow_json}

Current XML with errors:
{state.draft_xml}

Validation errors:
{errors_json}

Return the corrected XML."""

                response = await agent.run(prompt)

                # Clean up response
                xml_str = response.strip()
                if xml_str.startswith("```"):
                    xml_str = xml_str.split("```")[1]
                    if xml_str.startswith("xml"):
                        xml_str = xml_str[3:]
                    xml_str = xml_str.strip()

                state.draft_xml = xml_str
                logger.info(f"Stage 4: Repair generated {len(xml_str)} chars")
        except Exception as e:
            state.error_message = f"Stage 4 failed: {e}"
            logger.exception(f"Stage 4: Exception - {e}")
            return state

        elapsed = time.time() - start_time
        logger.info(f"Stage 4: Repair attempt completed in {elapsed:.2f}s")

        # Re-validate
        return await self.validate_xml(state)

    async def run(
        self, user_input: str, output_format: str = "bpmn", max_repairs: int = 3
    ) -> PipelineState:
        """Execute the full pipeline."""
        state = PipelineState(
            user_input=user_input, output_format=output_format, max_repairs=max_repairs
        )

        # Sequential execution
        state = await self.parse_intent(state)
        state = await self.generate_xml(state)
        state = await self.validate_xml(state)

        # Repair loop if needed
        while state.validation_result and not state.validation_result.valid:
            if state.repair_attempts >= state.max_repairs:
                break
            state = await self.repair_xml(state)

        return state


async def demo():
    """Demo the pipeline with a sample input."""
    pipeline = WorkflowPipeline(use_github_copilot=False)

    sample_input = """
    Create a customer onboarding workflow:
    1. Receive customer registration request
    2. Validate customer information
    3. If validation fails, send rejection email and end
    4. If validation passes, create customer account
    5. Send welcome email
    6. Complete onboarding
    """

    print("=" * 60)
    print("AI-Assisted Workflow Authoring Demo")
    print("=" * 60)
    print(f"\nInput:\n{sample_input}")
    print("\n" + "-" * 60)

    result = await pipeline.run(sample_input, output_format="bpmn")

    if result.error_message:
        print(f"\nError: {result.error_message}")
    else:
        print("\nGenerated Workflow JSON:")
        if result.workflow_json:
            print(result.workflow_json.model_dump_json(indent=2))

        print("\n" + "-" * 60)
        print("\nGenerated BPMN XML:")
        print(result.final_xml or result.draft_xml)

        if result.validation_result:
            print("\n" + "-" * 60)
            print(f"\nValidation: {'PASSED' if result.validation_result.valid else 'FAILED'}")
            if result.validation_result.warnings:
                print("Warnings:")
                for w in result.validation_result.warnings:
                    print(f"  - {w.message}")


if __name__ == "__main__":
    asyncio.run(demo())
