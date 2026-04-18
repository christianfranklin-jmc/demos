#!/usr/bin/env bash
# Setup and verify the dbt MCP server for agent integration.
#
# The dbt MCP server (dbt-labs/dbt-mcp v1.9.3) provides 40+ tools
# for dbt project management. It runs as a sidecar or Gateway endpoint.
#
# Prerequisites:
#   - uv (or uvx) installed
#   - dbt Cloud or Core credentials
#
# Usage:
#   ./scripts/setup-dbt-mcp.sh [--verify]

set -euo pipefail

echo "=== dbt MCP Server Setup ==="

# Check uvx is available
if ! command -v uvx &> /dev/null; then
    echo "ERROR: uvx not found. Install with: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

echo "✓ uvx found: $(which uvx)"

# Install dbt-mcp
echo ""
echo "Installing dbt-mcp..."
uvx install dbt-mcp 2>/dev/null || echo "dbt-mcp already installed or install via uvx run"

# Verify
if [[ "${1:-}" == "--verify" ]]; then
    echo ""
    echo "Verifying dbt-mcp tools..."
    echo '{"jsonrpc":"2.0","method":"tools/list","id":1}' | timeout 10 uvx dbt-mcp 2>/dev/null | head -20 || {
        echo ""
        echo "NOTE: dbt-mcp requires DBT_HOST and DBT_TOKEN env vars for full operation."
        echo "Set these in .env:"
        echo "  DBT_HOST=<your-dbt-cloud-host>"
        echo "  DBT_TOKEN=<your-dbt-cloud-token>"
        echo "  DBT_PROD_ENV_ID=<environment-id>"
    }
fi

echo ""
echo "=== Setup Complete ==="
echo "To use dbt MCP with agents, ensure these env vars are set:"
echo "  DBT_HOST, DBT_TOKEN, DBT_PROD_ENV_ID"
