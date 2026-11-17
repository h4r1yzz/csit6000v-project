"""Shared FitPilot tools for the LLM orchestrator and MCP server.

These wrap existing catalog/DB helpers. Tools are read-oriented except where noted;
plan activation remains an explicit UI/API approval step.
"""
from __future__ import annotations

import json
from typing import Any, Callable, Optional

from . import agents, db


ToolHandler = Callable[[dict[str, Any]], Any]

TOOL_SPECS: list[dict[str, Any]] = [
    {
        'name': 'get_profile',
        'description': 'Read the saved FitPilot profile: goals, schedule, equipment, diet, budget, and limitations.',
        'parameters': {'type': 'object', 'properties': {}, 'additionalProperties': False},
    },
    {
        'name': 'get_recent_progress',
        'description': 'Read this week\'s workout logs and the latest pose-session summary if one exists.',
        'parameters': {'type': 'object', 'properties': {}, 'additionalProperties': False},
    },
    {
        'name': 'search_exercises',
        'description': 'Search the exercise catalog. When available_only is true, apply equipment, experience, and limitation filters.',
        'parameters': {
            'type': 'object',
            'properties': {
                'query': {'type': 'string', 'description': 'Optional name substring filter.'},
                'available_only': {'type': 'boolean', 'description': 'If true, only return exercises valid for the current profile.'},
            },
            'additionalProperties': False,
        },
    },
    {
        'name': 'search_recipes',
        'description': 'Search the recipe catalog. When compatible_only is true, apply diet, allergy, and budget-compatible filters.',
        'parameters': {
            'type': 'object',
            'properties': {
                'query': {'type': 'string', 'description': 'Optional name or ingredient substring filter.'},
                'compatible_only': {'type': 'boolean', 'description': 'If true, only return diet/allergy-compatible recipes.'},
            },
            'additionalProperties': False,
        },
    },
    {
        'name': 'list_affordable_menus',
        'description': 'List pre-validated weekly menu options that already pass diet and budget checks.',
        'parameters': {'type': 'object', 'properties': {}, 'additionalProperties': False},
    },
    {
        'name': 'get_clarifications',
        'description': 'List coordinator clarification notes when preferences are vague or catalogs cannot satisfy constraints.',
        'parameters': {'type': 'object', 'properties': {}, 'additionalProperties': False},
    },
    {
        'name': 'validate_plan_draft',
        'description': 'Run deterministic constraint checks on a candidate workout/meal plan draft. Does not save or activate the plan.',
        'parameters': {
            'type': 'object',
            'properties': {
                'workouts': {'type': 'array', 'description': 'Workout sessions with day, focus, duration_minutes, exercises.'},
                'meals': {'type': 'array', 'description': 'Meal selections with catalog fields and servings_per_week.'},
                'estimated_weekly_cost': {'type': 'number'},
                'budget_currency': {'type': 'string', 'enum': ['USD', 'HKD']},
            },
            'required': ['workouts', 'meals', 'estimated_weekly_cost', 'budget_currency'],
            'additionalProperties': False,
        },
    },
    {
        'name': 'run_specialist',
        'description': 'Run one FitPilot specialist agent (goal_planning, exercise_planning, nutrition, exercise_feedback, evaluation_adaptation) and return its structured output.',
        'parameters': {
            'type': 'object',
            'properties': {
                'agent_id': {
                    'type': 'string',
                    'enum': ['goal_planning', 'exercise_planning', 'nutrition', 'exercise_feedback', 'evaluation_adaptation'],
                },
                'message': {'type': 'string', 'description': 'Optional user question passed to the specialist.'},
            },
            'required': ['agent_id'],
            'additionalProperties': False,
        },
    },
]


def openai_tools() -> list[dict[str, Any]]:
    return [
        {
            'type': 'function',
            'function': {
                'name': spec['name'],
                'description': spec['description'],
                'parameters': spec['parameters'],
            },
        }
        for spec in TOOL_SPECS
    ]


def _public_exercise(row: dict) -> dict:
    return {key: row[key] for key in ('id', 'name', 'difficulty', 'equipment', 'duration_minutes') if key in row}


def _public_recipe(row: dict) -> dict:
    keys = ('id', 'name', 'calories', 'protein_g', 'cost', 'dietary_tags', 'ingredients')
    return {key: row[key] for key in keys if key in row}


def execute(name: str, arguments: Optional[dict[str, Any]] = None, *, ctx: Optional[dict] = None) -> Any:
    """Execute one tool by name. Raises KeyError for unknown tools."""
    args = arguments or {}
    if not isinstance(args, dict):
        raise ValueError('Tool arguments must be an object')
    handlers: dict[str, ToolHandler] = {
        'get_profile': lambda _: agents.profile(),
        'get_recent_progress': _get_recent_progress,
        'search_exercises': lambda payload: _search_exercises(payload, ctx),
        'search_recipes': lambda payload: _search_recipes(payload, ctx),
        'list_affordable_menus': lambda _: _list_menus(ctx),
        'get_clarifications': lambda _: agents.planning_clarifications(ctx or agents.context()),
        'validate_plan_draft': lambda payload: _validate_draft(payload, ctx),
        'run_specialist': lambda payload: _run_specialist(payload, ctx),
    }
    if name not in handlers:
        raise KeyError(name)
    return handlers[name](args)


def execute_json(name: str, arguments: Optional[dict[str, Any]] = None, *, ctx: Optional[dict] = None) -> str:
    try:
        result = execute(name, arguments, ctx=ctx)
        return json.dumps(result, default=str)
    except Exception as exc:  # noqa: BLE001 - tool errors become observations for the model
        return json.dumps({'error': str(exc), 'tool': name})


def _get_recent_progress(_: dict) -> dict:
    ctx = agents.context()
    pose = ctx.get('pose_session')
    return {
        'recent_activity': ctx['recent_activity'],
        'pose_session': None if not pose else {
            'id': pose.get('id'),
            'exercise': pose.get('exercise'),
            'reps': pose.get('reps'),
            'duration_seconds': pose.get('duration_seconds'),
            'average_confidence': pose.get('average_confidence'),
            'form_cues': pose.get('form_cues', [])[:5],
        },
        'active_plan_present': bool(ctx.get('active_plan')),
    }


def _search_exercises(args: dict, ctx: Optional[dict]) -> list[dict]:
    context = ctx or agents.context()
    rows = agents.available_exercises(context) if args.get('available_only', True) else context['exercise_catalog']
    query = str(args.get('query') or '').strip().lower()
    if query:
        rows = [row for row in rows if query in row['name'].lower()]
    return [_public_exercise(row) for row in rows[:30]]


def _search_recipes(args: dict, ctx: Optional[dict]) -> list[dict]:
    context = ctx or agents.context()
    rows = agents.compatible_recipes(context) if args.get('compatible_only', True) else context['recipe_catalog']
    query = str(args.get('query') or '').strip().lower()
    if query:
        rows = [
            row for row in rows
            if query in row['name'].lower() or query in row.get('ingredients', '').lower()
        ]
    return [_public_recipe(row) for row in rows[:30]]


def _list_menus(ctx: Optional[dict]) -> list[dict]:
    context = ctx or agents.context()
    menus = agents.nutrition_options(context)
    return [
        {'menu_id': menu_id, 'estimated_weekly_cost': agents.menu_cost(meals), 'meals': meals}
        for menu_id, meals in menus.items()
    ]


def _validate_draft(args: dict, ctx: Optional[dict]) -> dict:
    context = ctx or agents.context()
    candidate = {
        'workouts': args['workouts'],
        'meals': args['meals'],
        'estimated_weekly_cost': args['estimated_weekly_cost'],
        'budget_currency': args['budget_currency'],
    }
    return agents.validate_plan(candidate, context)


def _run_specialist(args: dict, ctx: Optional[dict]) -> dict:
    agent_id = args['agent_id']
    if agent_id not in agents.MODELS:
        raise KeyError(agent_id)
    context = ctx or agents.context()
    run = agents.run_agent(agent_id, context, str(args.get('message') or ''))
    return {
        'agent_id': agent_id,
        'source': run['source'],
        'output': run['output'],
        'error': run.get('error'),
    }


def ensure_db() -> None:
    db.initialize()
