"""Minimal OpenAI-compatible client for TACC Qwen and configurable local models."""
from __future__ import annotations

import json
import math
from http.client import HTTPException
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


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


def ask(messages: list[dict[str, str]], *, temperature: float = 0.2, max_tokens: int = 1600, timeout_override: float = None, structured_schema: dict = None) -> str:
    cfg = configuration()
    if not cfg['configured']:
        raise ModelUnavailable('A valid LLM_BASE_URL or QWEN_BASE_URL and model must be configured')
    try:
        timeout = float(timeout_override if timeout_override is not None else os.getenv('LLM_TIMEOUT_SECONDS', os.getenv('QWEN_TIMEOUT_SECONDS', '45')))
        timeout = min(120.0, max(1.0, timeout)) if math.isfinite(timeout) else 45.0
    except (ValueError, TypeError):
        timeout = 45.0
    payload = {'model': cfg['model'], 'messages': messages, 'temperature': temperature, 'max_tokens': max_tokens}
    # Qwen's extension is not sent to generic providers that may reject unknown fields.
    if cfg['provider'] == 'tacc_qwen':
        payload['chat_template_kwargs'] = {'enable_thinking': False}
        if structured_schema is not None:
            payload['structured_outputs'] = {'json': structured_schema}
    headers = {'Content-Type': 'application/json'}
    key = os.getenv('LLM_API_KEY', '').strip()
    if key:
        headers['Authorization'] = f'Bearer {key}'
    req = Request(f"{cfg['base_url']}/chat/completions", data=json.dumps(payload).encode(), headers=headers)
    try:
        with urlopen(req, timeout=timeout) as response:
            data = json.load(response)
        answer = data['choices'][0]['message']['content']
        if not isinstance(answer, str) or not answer.strip():
            raise ModelUnavailable('The model returned an empty answer')
        return answer.strip()
    except (HTTPError, HTTPException, URLError, TimeoutError, OSError, ValueError, KeyError, IndexError, TypeError) as exc:
        raise ModelUnavailable('The configured model could not complete the request; local rules were used') from exc
