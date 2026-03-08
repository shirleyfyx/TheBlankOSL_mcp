# Evaluation Framework

Evaluates the LLM's ability to select the correct MCP tools and arguments given a user prompt.
The framework uses **mock tool schemas** — no live MCP servers are needed.

## How It Works

1. Each test case in `dataset.yaml` defines:
   - A **user prompt** (e.g., "Read /app/config.json")
   - A list of **available tools** (mock schemas the LLM can choose from)
   - An **expected trajectory** (the tools + args the LLM should select)
   - An **eval type** (`exact_match`, `unordered_subset`, or `no_tools_called`)

2. The runner sends the prompt and tool schemas to Gemini, intercepts the tool calls (without executing them), and grades the result.

## Prerequisites

- Docker (with the project image built)
- A valid **Gemini API key**

Set the API key in the CLI config (inside the container):
```bash
blankosl_cli config --gemini-api-key <your_key>
```

## Running the Evaluation

### From inside the Docker container

```bash
docker compose up -d mcp-shared
docker exec -it mcp-shared bash
```

Then run:
```bash
GEMINI_API_KEY=<your_key> PYTHONPATH=/app/TheBlankOSL_mcp \
  python -m mcp_client.eval.runner \
  --dataset /app/TheBlankOSL_mcp/mcp_client/eval/dataset.yaml
```

### From the host (one-liner)

```bash
docker compose run --rm \
  -e GEMINI_API_KEY=<your_key> \
  -e PYTHONPATH=/app/TheBlankOSL_mcp \
  mcp-shared python -m mcp_client.eval.runner \
  --dataset /app/TheBlankOSL_mcp/mcp_client/eval/dataset.yaml
```

### CLI Options

| Flag | Default | Description |
|------|---------|-------------|
| `--dataset`, `-d` | `TheBlankOSL_mcp/mcp_client/eval/dataset.yaml` | Path to the YAML dataset |
| `--model`, `-m` | `gemini-2.5-flash` | Gemini model to use |

## Eval Types

| Type | Behavior |
|------|----------|
| `exact_match` | LLM must call the exact tools in the exact order with exact arguments |
| `unordered_subset` | LLM must call all expected tools (order doesn't matter) |
| `no_tools_called` | LLM should refuse and not call any tools |

## Adding Test Cases

Add new entries to `dataset.yaml`. Each case needs:

```yaml
- id: "eval_XXX_description"
  category: "filesystem"            # Category for grouping
  description: "What this tests."
  user_prompt: "The prompt to send."
  available_tools:                   # Mock tool schemas
    - name: "server.tool_name"
      description: "What the tool does."
      input_schema:
        type: "object"
        properties:
          arg_name: { type: "string" }
        required: ["arg_name"]
  expected_trajectory:               # What the LLM should call
    - tool_name: "server.tool_name"
      arguments:
        arg_name: "expected_value"
  eval_type: "exact_match"
```

## Project Structure

```
eval/
├── README.md        # This file
├── dataset.yaml     # Test cases
├── models.py        # Pydantic data models
└── runner.py        # Evaluation runner
```
