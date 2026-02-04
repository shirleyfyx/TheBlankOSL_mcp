FROM python:3.13-slim-bookworm

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    wkhtmltopdf \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy and install Python dependencies
COPY TheBlankOSL_mcp/pyproject.toml TheBlankOSL_mcp/
COPY TheBlankOSL_mcp/README.md TheBlankOSL_mcp/
COPY TheBlankOSL_mcp/mcp_client TheBlankOSL_mcp/mcp_client
COPY TheBlankOSL_mcp/mcp_servers TheBlankOSL_mcp/mcp_servers
RUN pip install --no-cache-dir ./TheBlankOSL_mcp

COPY . .

ENV PYTHONPATH=/app
