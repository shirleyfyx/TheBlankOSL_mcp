"""
Data models for the MCP evaluation framework.

Defines the structure of evaluation test cases and their expected trajectories.
"""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class EvalType(str, Enum):
    """
    Different types of evaluation grading logic.
    """
    EXACT_MATCH = "exact_match"
    # The LLM must call the exact tools in the exact order with the exact arguments.

    UNORDERED_SUBSET = "unordered_subset"
    # The LLM must call all expected tools, but the order does not matter.

    NO_TOOLS_CALLED = "no_tools_called"
    # The LLM should refuse to call any tools (e.g., for safety violations).


class ExpectedTrajectoryItem(BaseModel):
    """
    A single expected tool call in a trajectory.
    """
    tool_name: str = Field(description="The fully qualified name of the tool (e.g., 'filesystem.read_file')")
    arguments: Optional[Dict[str, Any]] = Field(
        default=None,
        description="The exact arguments expected. If None, arguments are not strictly evaluated."
    )

    # Placeholders for future advanced evaluation:
    # argument_validators: Optional[Dict[str, str]] = None


class EvalSetupState(BaseModel):
    """
    Instructions for the sandbox to prepare the environment before the test.
    Only applicable if running the eval against a real sandbox docker container.
    """
    files: Optional[Dict[str, str]] = Field(
        default=None,
        description="A dictionary mapping absolute file paths to their desired string content."
    )


class EvalTestCase(BaseModel):
    """
    A single evaluation test case.
    """
    id: str = Field(description="A unique identifier for the test case.")
    category: str = Field(description="The category of the test (e.g., 'file_operations', 'multi_step').")
    description: str = Field(description="Human-readable description of what this test evaluates.")

    user_prompt: str = Field(description="The prompt fed to the LLM.")

    available_tools: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="The list of mock tool schemas available to the LLM for this test case."
    )

    expected_trajectory: List[ExpectedTrajectoryItem] = Field(
        default_factory=list,
        description="The sequence of tool calls the LLM is expected to make."
    )

    eval_type: EvalType = Field(
        default=EvalType.EXACT_MATCH,
        description="How to grade the LLM's actual trajectory against the expected one."
    )

    setup_state: Optional[EvalSetupState] = Field(
        default=None,
        description="Optional state to setup before running the eval."
    )


class EvalDataset(BaseModel):
    """
    A collection of evaluation test cases.
    """
    cases: List[EvalTestCase]
