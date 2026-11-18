"""Minimal OpenAI-compatible client for TACC Qwen and configurable local models."""
from __future__ import annotations

import json
import math
from http.client import HTTPException
import os
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from . import db


class ModelUnavailable(RuntimeError):
    pass


def configuration() -> dict:
    generic = bool(os.getenv('LLM_BASE_URL', '').strip())
    base = os.getenv('LLM_BASE_URL' if generic else 'QWEN_BASE_URL', '').strip().rstrip('/')
    model = os.getenv('LLM_MODEL' if generic else 'QWEN_MODEL', 'qwen3.8-27b').strip()
    valid = False
    if base:
        try:
            parts = urlsplit(base)
            valid = parts.scheme in ('http', 'https') and bool(parts.hostname) and not parts.query and not parts.fragment and not parts.username and not parts.password and not any(c.isspace() for c in base)
            if parts.port is not None and not 1 <= parts.port <= 65535:
                valid = False
        except ValueError:
            pass
    return {'configured': bool(base and model and valid), 'model': model, 'provider': 'openai_compatible' if generic else 'tacc_qwen', 'base_url': base, 'valid_url': bool(valid), 'source': 'llm' if generic else 'tacc_qwen'}


def _timeout(timeout_override: Optional[float] = None) -> float:
    try:
        timeout = float(timeout_override if timeout_override is not None else os.getenv('LLM_TIMEOUT_SECONDS', os.getenv('QWEN_TIMEOUT_SECONDS', '45')))
        return min(120.0, max(1.0, timeout)) if math.isfinite(timeout) else 45.0
    except (ValueError, TypeError):
        return 45.0


def chat(
    messages: list[dict[str, Any]],
    *,
    temperature: float = 0.2,
    max_tokens: int = 1600,
    timeout_override: float = None,
    structured_schema: dict = None,
    tools: Optional[list[dict[str, Any]]] = None,
    tool_choice: str | dict = 'auto',
    agent_id: Optional[str] = None,
    agent_run_id: Optional[int] = None,
) -> dict[str, Any]:
    """Call chat/completions and return the assistant message object (may include tool_calls)."""
    cfg = configuration()
    timeout = _timeout(timeout_override)
    payload: dict[str, Any] = {
        'model': cfg['model'],
        'messages': messages,
        'temperature': temperature,
        'max_tokens': max_tokens,
    }
    if tools:
        payload['tools'] = tools
        payload['tool_choice'] = tool_choice
    # Qwen's extension is not sent to generic providers that may reject unknown fields.
    if cfg['provider'] == 'tacc_qwen':
        payload['chat_template_kwargs'] = {'enable_thinking': False}
        if structured_schema is not None and not tools:
            payload['structured_outputs'] = {'json': structured_schema}
    prompt_id = None
    if agent_id is not None:
        # Store the model input in the caller's database. HTTP headers and endpoint
        # credentials are transport settings and never enter the stored body.
        prompt_id = db.execute(
            'INSERT INTO model_prompts(agent_id,agent_run_id,provider,model,request_json,status) '
            'VALUES(?,?,?,?,?,?)',
            (agent_id, agent_run_id, cfg['provider'], cfg['model'], db.json_dump(payload),
             'pending' if cfg['configured'] else 'unconfigured'),
        )
    if not cfg['configured']:
        raise ModelUnavailable('A valid LLM_BASE_URL or QWEN_BASE_URL and model must be configured')
    try:
        reply = _send_chat(cfg, payload, timeout)
    except ModelUnavailable:
        if prompt_id is not None:
            db.execute('UPDATE model_prompts SET status=? WHERE id=?', ('failed', prompt_id))
        raise
    if prompt_id is not None:
        db.execute('UPDATE model_prompts SET status=? WHERE id=?', ('answered', prompt_id))
    return reply


def _send_chat(cfg: dict, payload: dict, timeout: float) -> dict[str, Any]:
    headers = {'Content-Type': 'application/json'}
    key = os.getenv('LLM_API_KEY', '').strip()
    if key:
        headers['Authorization'] = f'Bearer {key}'
    req = Request(f"{cfg['base_url']}/chat/completions", data=json.dumps(payload).encode(), headers=headers)
    try:
        with urlopen(req, timeout=timeout) as response:
            data = json.load(response)
        message = data['choices'][0]['message']
        if not isinstance(message, dict):
            raise ModelUnavailable('The model returned an invalid message')
        content = message.get('content')
        tool_calls = message.get('tool_calls') or []
        if tool_calls:
            return {'role': 'assistant', 'content': content, 'tool_calls': tool_calls, 'source': cfg['source']}
        if not isinstance(content, str) or not content.strip():
            raise ModelUnavailable('The model returned an empty answer')
        return {'role': 'assistant', 'content': content.strip(), 'source': cfg['source']}
    except (HTTPError, HTTPException, URLError, TimeoutError, OSError, ValueError, KeyError, IndexError, TypeError) as exc:
        raise ModelUnavailable('The configured model could not complete the request; local rules were used') from exc


def ask(messages: list[dict[str, Any]], *, temperature: float = 0.2, max_tokens: int = 1600,
        timeout_override: float = None, structured_schema: dict = None,
        agent_id: Optional[str] = None, agent_run_id: Optional[int] = None) -> str:
    message = chat(
        messages,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout_override=timeout_override,
        structured_schema=structured_schema,
        agent_id=agent_id,
        agent_run_id=agent_run_id,
    )
    content = message.get('content')
    if not isinstance(content, str) or not content.strip():
        raise ModelUnavailable('The model returned an empty answer')
    return content.strip()
