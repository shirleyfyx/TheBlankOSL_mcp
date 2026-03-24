"""
Evaluation Framework Runner

Loads the evaluation dataset, feeds prompts to the LLM, intercepts the tool calls,
and grades them against expected behaviors.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import typer
import yaml
from google import genai
from pydantic import ValidationError
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from mcp_client.eval.models import (
    EvalDataset,
    EvalTestCase,
    EvalType,
    ExpectedTrajectoryItem,
)

app = typer.Typer(
    help="Run the MCP evaluation suite.",
    add_completion=False,
    rich_markup_mode="rich",
)
console = Console()
logger = logging.getLogger(__name__)


def load_dataset(dataset_path: Path) -> EvalDataset:
    """Loads and validates the YAML dataset."""
    try:
        with open(dataset_path, "r") as f:
            data = yaml.safe_load(f)

        return EvalDataset.model_validate(data)
    except FileNotFoundError:
        console.print(f"[red]Error:[/red] Dataset not found at {dataset_path}")
        raise typer.Exit(1)
    except yaml.YAMLError as e:
        console.print(f"[red]Error parsing YAML:[/red] {e}")
        raise typer.Exit(1)
    except ValidationError as e:
        console.print("[red]Dataset validation failed:[/red]")
        console.print(e)
        raise typer.Exit(1)


def compare_arguments(expected: Dict[str, Any], actual: Dict[str, Any]) -> bool:
    """
    Checks if actual arguments match expected arguments.
    Currently does a strict match. Could be expanded for partial or validator matches.
    """
    # Simply check if the expected dict is a subset of the actual dict for now
    for key, value in expected.items():
        if key not in actual:
            return False

        # Handle lists (e.g., input_paths)
        if isinstance(value, list) and isinstance(actual[key], list):
            if sorted(value) != sorted(actual[key]):
                return False
        # Handle simple values
        elif actual[key] != value:
            return False

    return True


def grade_trajectory(
    test_case: EvalTestCase, actual_tool_calls: List[Tuple[str, Dict[str, Any]]]
) -> Tuple[bool, str]:
    """
    Compares the list of (tool_name, arguments) returned by the LLM
    against the expected trajectory based on the evaluation type.

    Returns: (passed, reason_string)
    """
    expected = test_case.expected_trajectory
    actual = actual_tool_calls

    # 1. NO_TOOLS_CALLED
    if test_case.eval_type == EvalType.NO_TOOLS_CALLED:
        if len(actual) == 0:
            return True, "Passed: No tools were called as expected."
        return (
            False,
            f"Failed: Expected 0 tools, but {len(actual)} were called ({[t[0] for t in actual]}).",
        )

    # 2. EXACT_MATCH
    if test_case.eval_type == EvalType.EXACT_MATCH:
        if len(actual) != len(expected):
            return (
                False,
                f"Failed: Expected {len(expected)} tool calls, got {len(actual)}.",
            )

        for i, (exp, act) in enumerate(zip(expected, actual)):
            act_name, act_args = act
            if exp.tool_name != act_name:
                return (
                    False,
                    f"Failed at step {i + 1}: Expected tool '{exp.tool_name}', got '{act_name}'.",
                )

            if exp.arguments and not compare_arguments(exp.arguments, act_args):
                return (
                    False,
                    f"Failed at step {i + 1}: Args mismatch. Expected {exp.arguments}, got {act_args}.",
                )

        return True, "Passed: Exact match on tools and arguments."

    # 3. UNORDERED_SUBSET
    if test_case.eval_type == EvalType.UNORDERED_SUBSET:
        matched_expected = []
        for exp in expected:
            match_found = False
            for act_name, act_args in actual:
                if act_name == exp.tool_name:
                    if not exp.arguments or compare_arguments(exp.arguments, act_args):
                        match_found = True
                        break
            if not match_found:
                return (
                    False,
                    f"Failed: Expected tool '{exp.tool_name}' with args {exp.arguments} was not found in actual calls.",
                )
            matched_expected.append(True)

        if len(matched_expected) == len(expected):
            return True, "Passed: All expected tools were found in the trajectory."

    return False, f"Unknown evaluation type: {test_case.eval_type}"


async def run_evaluation(dataset_path: Path, model_name: str) -> None:
    """Orchestrates the evaluation run."""

    console.print(
        Panel(
            f"Running MCP Evaluation Suite\n[dim]Dataset: {dataset_path}\nModel: {model_name}[/dim]"
        )
    )

    # 1. Load Dataset
    dataset = load_dataset(dataset_path)
    console.print(f"Loaded {len(dataset.cases)} test cases.\n")

    # 2. Setup LLM Client
    client = genai.Client()

    results = []

    # 3. Run Test Cases
    for case in dataset.cases:
        console.print(
            f"▶️  [bold cyan]Running {case.id}[/bold cyan] [dim]({case.category})[/dim]"
        )

        # Tools are now provided directly inline in the mock dataset
        available_tools = case.available_tools
        if not available_tools and case.eval_type != EvalType.NO_TOOLS_CALLED:
            console.print(
                "  [yellow]WARNING: No available mock tools provided in test case.[/yellow]"
            )

        # Execute LLM step
        try:
            # Prepare tools for the SDK
            sdk_tools = []
            if available_tools:
                for tool in available_tools:
                    # Convert to minimal google.genai.types.FunctionDeclaration-like dictionary structure
                    # Because we are using the new SDK, we need to pass the tools in a specific format
                    from google.genai import types

                    properties = {}
                    required = []

                    # Basic mapping of our arbitrary schema to the GenAI SDK
                    if "input_schema" in tool and "properties" in tool["input_schema"]:
                        for prop_name, prop_details in tool["input_schema"][
                            "properties"
                        ].items():
                            prop_type = prop_details.get("type", "string").upper()
                            if prop_type == "NUMBER":
                                prop_type = (
                                    "ARRAY" if prop_details.get("items") else "NUMBER"
                                )  # simplify mapping

                            properties[prop_name] = types.Schema(
                                type=getattr(types.Type, prop_type, types.Type.STRING),
                                description=prop_details.get("description", ""),
                            )
                        required = tool["input_schema"].get("required", [])

                    sdk_tool = types.Tool(
                        function_declarations=[
                            types.FunctionDeclaration(
                                name=tool["name"].replace(
                                    ".", "_"
                                ),  # SDK doesn't like dots in names
                                description=tool.get("description", ""),
                                parameters=types.Schema(
                                    type=types.Type.OBJECT,
                                    properties=properties,
                                    required=required,
                                )
                                if properties
                                else None,
                            )
                        ]
                    )
                    sdk_tools.append(sdk_tool)

            config = types.GenerateContentConfig(
                tools=sdk_tools if sdk_tools else None, temperature=0.0
            )

            response = client.models.generate_content(
                model=model_name, contents=case.user_prompt, config=config
            )

            # Extract actual tool calls
            actual_calls = []

            if (
                response.candidates
                and response.candidates[0].content
                and response.candidates[0].content.parts
            ):
                for part in response.candidates[0].content.parts:
                    if part.function_call:
                        # Restore original name (dot notation) if possible
                        original_name = part.function_call.name.replace("_", ".")
                        # Find the actual tool to see if we guessed the dot correctly
                        for t in available_tools:
                            if t["name"].replace(".", "_") == part.function_call.name:
                                original_name = t["name"]
                                break

                        actual_calls.append(
                            (
                                original_name,
                                dict(
                                    part.function_call.args
                                    if part.function_call.args
                                    else {}
                                ),
                            )
                        )

            # Grade
            passed, reason = grade_trajectory(case, actual_calls)
            results.append(
                {
                    "case": case,
                    "passed": passed,
                    "reason": reason,
                    "actual": actual_calls,
                }
            )

            if passed:
                console.print(f"  ✅ [green]{reason}[/green]")
            else:
                console.print(f"  ❌ [red]{reason}[/red]")
                if actual_calls:
                    console.print(f"     [dim]Actual calls: {actual_calls}[/dim]")

        except Exception as e:
            console.print(f"  ❌ [red]Error during LLM execution:[/red] {e}")
            results.append(
                {"case": case, "passed": False, "reason": str(e), "actual": []}
            )

    # 4. Print Summary Report
    console.print("\n" + "=" * 50)
    console.print("[bold]Evaluation Summary[/bold]")

    passed_count = sum(1 for r in results if r["passed"])
    total = len(dataset.cases)

    table = Table(show_header=True)
    table.add_column("Test ID")
    table.add_column("Result")
    table.add_column("Reason")

    for r in results:
        status = "[green]PASS[/green]" if r["passed"] else "[red]FAIL[/red]"
        table.add_row(r["case"].id, status, r["reason"])

    console.print(table)

    score_color = "green" if passed_count == total else "yellow"
    console.print(
        f"\nFinal Score: [{score_color}]{passed_count}/{total}[/{score_color}] passed."
    )


@app.callback(invoke_without_command=True)
def main(
    dataset: Path = typer.Option(
        Path("TheBlankOSL_mcp/mcp_client/eval/dataset.yaml"),
        "--dataset",
        "-d",
        help="Path to the evaluation dataset.",
    ),
    model: str = typer.Option(
        "gemini-2.5-flash",
        "--model",
        "-m",
        help="The Gemini model to use for evaluation.",
    ),
) -> None:
    """Run the evaluation framework against mock tools provided in the dataset."""
    import asyncio

    asyncio.run(run_evaluation(dataset, model))


if __name__ == "__main__":
    app()
