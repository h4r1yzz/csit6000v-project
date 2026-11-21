"""Tool-calling coordinator for FitPilot chat and MCP-aligned agent loops.

The specialist pipeline in agents.workflow_plan remains the plan generator.
This orchestrator lets a model call shared tools (profile, catalogs, validation,
specialists) in a bounded loop before answering the user.
"""
from __future__ import annotations

import json
from typing import Any, Optional

from . import agents, tacc, tools

MAX_TOOL_ROUNDS = 5

ORCHESTRATOR_SYSTEM = (
    "You are FitPilot's Central Orchestrator. "
    'Use tools to inspect the profile, catalogs, progress, clarifications, and specialist outputs. '
    'Treat recent questions as background. Prioritize the current request and saved profile constraints. '
    'Prefer tools over guessing. Provide general wellness guidance only; never diagnose injuries. '
    'Do not claim to have seen video. Do not tell the user a plan was saved unless they approved it in the UI. '
    'When enough evidence is gathered, answer clearly in plain language for the user.'
)


def _parse_arguments(raw: Any) -> dict[str, Any]:
    if raw is None or raw == '':
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        value = json.loads(raw) if raw.strip() else {}
        if not isinstance(value, dict):
            raise ValueError('Tool arguments must be a JSON object')
        return value
    raise ValueError('Tool arguments must be a JSON object')


def run_orchestrator(message: str, *, ctx: Optional[dict] = None, max_rounds: int = MAX_TOOL_ROUNDS) -> dict[str, Any]:
    """Bounded tool-calling loop. Requires a configured, reachable model."""
    if not tacc.configuration()['configured']:
        raise tacc.ModelUnavailable('Configure QWEN_BASE_URL or LLM_BASE_URL to use the FitPilot coach.')
    context = ctx or agents.context()
    trace: list[dict[str, Any]] = []
    messages: list[dict[str, Any]] = [
        {'role': 'system', 'content': ORCHESTRATOR_SYSTEM},
        {
            'role': 'user',
            'content': json.dumps({
                'question': message,
                'profile': context['profile'],
                'recent_questions': context.get('recent_questions', []),
                'hint': 'Call tools as needed, then answer the user. Keep the final answer concise.',
            }),
        },
    ]
    if context.get('model_unavailable'):
        raise tacc.ModelUnavailable('Model unavailable earlier in this workflow')
    openai_tool_defs = tools.openai_tools()
    source = tacc.configuration()['source']
    try:
        for _ in range(max(1, max_rounds)):
            reply = tacc.chat(messages, tools=openai_tool_defs, max_tokens=1800, agent_id='orchestrator')
            source = reply.get('source') or source
            tool_calls = reply.get('tool_calls') or []
            if not tool_calls:
                answer = (reply.get('content') or '').strip()
                if not answer:
                    raise tacc.ModelUnavailable('The orchestrator returned an empty answer')
                return {
                    'answer': answer,
                    'source': source,
                    'agent_id': 'orchestrator',
                    'tool_trace': trace,
                    'requires_approval': False,
                }
            assistant_msg: dict[str, Any] = {'role': 'assistant', 'content': reply.get('content'), 'tool_calls': tool_calls}
            messages.append(assistant_msg)
            for call in tool_calls:
                function = call.get('function') or {}
                name = function.get('name') or ''
                call_id = call.get('id') or name
                try:
                    arguments = _parse_arguments(function.get('arguments'))
                    result_text = tools.execute_json(name, arguments, ctx=context)
                    ok = '"error"' not in result_text[:40]
                except (ValueError, TypeError, json.JSONDecodeError) as exc:
                    result_text = json.dumps({'error': str(exc), 'tool': name})
                    ok = False
                trace.append({'tool': name, 'arguments': function.get('arguments'), 'ok': ok, 'result_preview': result_text[:400]})
                messages.append({'role': 'tool', 'tool_call_id': call_id, 'content': result_text})
        # Tool budget exhausted: force a plain-language answer without more tools.
        answer = tacc.ask(
            messages + [{'role': 'user', 'content': 'Tool budget reached. Answer the user now without more tool calls.'}],
            max_tokens=1200,
            agent_id='orchestrator',
        )
        return {
            'answer': answer,
            'source': source,
            'agent_id': 'orchestrator',
            'tool_trace': trace,
            'requires_approval': False,
        }
    except tacc.ModelUnavailable:
        context['model_unavailable'] = True
        raise


def orchestrate_plan() -> dict[str, Any]:
    """Plan generation stays on the specialist pipeline; expose it under the orchestrator API."""
    result = agents.workflow_plan()
    result['agent_id'] = 'orchestrator'
    result['tool_trace'] = [
        {'tool': 'workflow_plan', 'arguments': {}, 'ok': True, 'result_preview': f"{len(result.get('steps', []))} specialist stages"}
    ]
    return result
