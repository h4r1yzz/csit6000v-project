#!/usr/bin/env python3
"""FitPilot MCP server — exposes the same tools used by the in-app orchestrator.

Run (from backend/, with the project venv):
  .venv/bin/python mcp_server.py

Cursor MCP example (stdio):
  command: /absolute/path/to/backend/.venv/bin/python
  args: [/absolute/path/to/backend/mcp_server.py]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / '.env')

from app import tools  # noqa: E402

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:  # pragma: no cover - newer package layout
    from mcp.server import MCPServer as FastMCP


mcp = FastMCP('FitPilot')


@mcp.tool()
def get_profile() -> str:
    """Read the saved FitPilot profile: goals, schedule, equipment, diet, budget, and limitations."""
    tools.ensure_db()
    return tools.execute_json('get_profile')


@mcp.tool()
def get_recent_progress() -> str:
    """Read this week's workout logs and the latest pose-session summary if one exists."""
    tools.ensure_db()
    return tools.execute_json('get_recent_progress')


@mcp.tool()
def search_exercises(query: str = '', available_only: bool = True) -> str:
    """Search the exercise catalog. When available_only is true, apply profile filters."""
    tools.ensure_db()
    return tools.execute_json('search_exercises', {'query': query, 'available_only': available_only})


@mcp.tool()
def search_recipes(query: str = '', compatible_only: bool = True) -> str:
    """Search the recipe catalog. When compatible_only is true, apply diet/allergy filters."""
    tools.ensure_db()
    return tools.execute_json('search_recipes', {'query': query, 'compatible_only': compatible_only})


@mcp.tool()
def list_affordable_menus() -> str:
    """List pre-validated weekly menu options that already pass diet and budget checks."""
    tools.ensure_db()
    return tools.execute_json('list_affordable_menus')


@mcp.tool()
def get_clarifications() -> str:
    """List coordinator clarification notes for vague or impossible preferences."""
    tools.ensure_db()
    return tools.execute_json('get_clarifications')


@mcp.tool()
def validate_plan_draft(workouts: list, meals: list, estimated_weekly_cost: float, budget_currency: str = 'USD') -> str:
    """Run deterministic constraint checks on a candidate plan. Does not save or activate it."""
    tools.ensure_db()
    return tools.execute_json(
        'validate_plan_draft',
        {
            'workouts': workouts,
            'meals': meals,
            'estimated_weekly_cost': estimated_weekly_cost,
            'budget_currency': budget_currency,
        },
    )


@mcp.tool()
def run_specialist(agent_id: str, message: str = '') -> str:
    """Run one FitPilot specialist and return its structured output."""
    tools.ensure_db()
    return tools.execute_json('run_specialist', {'agent_id': agent_id, 'message': message})


@mcp.tool()
def list_tools() -> str:
    """List FitPilot MCP tool names and descriptions."""
    return json.dumps([{'name': spec['name'], 'description': spec['description']} for spec in tools.TOOL_SPECS])


if __name__ == '__main__':
    tools.ensure_db()
    mcp.run()
