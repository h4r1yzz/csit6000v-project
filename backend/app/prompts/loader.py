"""Load Markdown prompt files that use XML tags for structure."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent

_PLACEHOLDERS = ('agent_name', 'task', 'schema_json')


def _flatten(element: ET.Element) -> str:
    """Turn nested XML into a tagged plain-text system prompt."""
    parts: list[str] = []
    for child in list(element):
        tag = child.tag.strip()
        text = ''.join(child.itertext()).strip()
        if not text:
            continue
        parts.append(f'<{tag}>\n{text}\n</{tag}>')
    if parts:
        return '\n\n'.join(parts)
    return ''.join(element.itertext()).strip()


@lru_cache(maxsize=32)
def _read_prompt(relative: str) -> str:
    path = ROOT / relative
    if not path.is_file():
        raise FileNotFoundError(f'Prompt file missing: {path}')
    root = ET.fromstring(path.read_text(encoding='utf-8'))
    return _flatten(root)


def _substitute(template: str, fields: dict[str, str]) -> str:
    """Replace {name} placeholders without interpreting braces inside values (e.g. JSON schema)."""
    result = template
    for key in _PLACEHOLDERS:
        token = '{' + key + '}'
        if token in result:
            if key not in fields:
                raise KeyError(f'Missing prompt placeholder: {key}')
            result = result.replace(token, fields[key])
    return result


def render(kind: str, *, agent_id: str = '', agent_name: str = '', schema_json: str = '') -> str:
    """Build a system prompt.

    kind:
      - 'orchestrator' — coach tool-calling system prompt
      - 'specialist' — base wrapper + specialists/{agent_id}.md task
    """
    if kind == 'orchestrator':
        return _read_prompt('orchestrator.md')
    if kind == 'specialist':
        if not agent_id or not agent_name:
            raise ValueError('specialist prompts require agent_id and agent_name')
        task = _read_prompt(f'specialists/{agent_id}.md')
        base = _read_prompt('specialist_base.md')
        return _substitute(
            base,
            {
                'agent_name': agent_name,
                'task': task,
                'schema_json': schema_json or '{}',
            },
        )
    raise ValueError(f'Unknown prompt kind: {kind}')
