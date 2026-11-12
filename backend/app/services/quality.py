"""Deterministic, local-only prompt quality and context-budget helpers.

Token counts are conservative estimates (not a model-specific tokenizer). The planner
reserves output/headroom and bounds all sections before sending them to Ollama.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Iterable

WORD = re.compile(r"\b[\w'-]+\b", re.UNICODE)


def estimated_tokens(text: str) -> int:
    """Conservative heuristic: >= one token per word and ~3 chars/token."""
    if not text:
        return 0
    return max(len(WORD.findall(text)), (len(text.encode('utf-8')) + 2) // 3)


def clip_tokens(text: str, tokens: int) -> str:
    if tokens <= 0:
        return ''
    if estimated_tokens(text) <= tokens:
        return text
    # Binary search by character, avoiding cuts inside multi-byte text.
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if estimated_tokens(text[:mid]) <= tokens:
            lo = mid
        else:
            hi = mid - 1
    return text[:lo].rstrip() + (' …' if lo > 0 else '')


@dataclass(frozen=True)
class ContextPlan:
    messages: list[dict[str, str]]
    diagnostics: dict


def assemble_context(system_sections: list[tuple[str, str]], history: list[dict[str, str]],
                     *, num_ctx: int, output_tokens: int, recent_minimum: int = 2) -> ContextPlan:
    """Assemble mandatory identity, prioritized references, and newest history.

    All content is local. Sections are tuples (name, text) in descending priority;
    the first is the authoritative character identity. Excludes overflowing history
    from the oldest side. Output tokens and fixed headroom are reserved.
    """
    if not system_sections:
        raise ValueError('A character identity section is required')
    if num_ctx < 512 or output_tokens < 1:
        raise ValueError('Invalid context window or output reservation')
    reserve = min(num_ctx - 128, output_tokens + max(96, num_ctx // 20))
    input_budget = num_ctx - reserve
    # Protect the final user message/most recent turn, even in long-running scenes.
    minimum = history[-max(1, recent_minimum):]
    min_budget = min(input_budget // 2, max(128, input_budget // 3))
    retained_latest = []
    remaining_min = min_budget
    for msg in reversed(minimum):
        role = msg['role']
        part = clip_tokens(msg['content'], max(0, remaining_min - 8))
        if part:
            retained_latest.append({'role': role, 'content': part})
            remaining_min -= estimated_tokens(part) + 8
        if remaining_min <= 8:
            break
    retained_latest.reverse()
    recent_cost = sum(estimated_tokens(m['content']) + 8 for m in retained_latest)
    system_budget = max(64, input_budget - recent_cost)
    sections = []
    used = 0
    section_info = []
    for index, (name, content) in enumerate(system_sections):
        available = max(0, system_budget - used - 12)
        # Never let optional sections crowd out mandatory identity.
        if index == 0:
            available = min(available, max(96, system_budget * 2 // 3))
        value = clip_tokens(content, available)
        if value:
            sections.append(value)
            used += estimated_tokens(value) + 12
        section_info.append({'name': name, 'estimated_tokens': estimated_tokens(value),
                             'truncated': bool(content) and value != content})
    prompt = '\n\n'.join(sections)
    allocated = estimated_tokens(prompt) + 8 + recent_cost
    remaining = max(0, input_budget - allocated)
    older = history[:max(0, len(history)-len(minimum))]
    chosen_older = []
    for msg in reversed(older):
        cost = estimated_tokens(msg['content']) + 8
        if cost > remaining:
            break
        chosen_older.append(msg)
        remaining -= cost
    chosen_older.reverse()
    selected = [{'role': 'system', 'content': prompt}] + chosen_older + retained_latest
    total = sum(estimated_tokens(m['content']) + 8 for m in selected)
    return ContextPlan(selected, {
        'method': 'conservative-estimate-not-model-tokenizer',
        'context_window': num_ctx, 'reserved_output_and_headroom': reserve,
        'input_budget': input_budget, 'estimated_input_tokens': total,
        'history_messages_included': len(chosen_older) + len(retained_latest),
        'history_messages_skipped': len(history) - len(chosen_older) - len(retained_latest),
        'sections': section_info,
    })


def rank_memories(memories: Iterable, query: str, limit: int = 8) -> list:
    """Token overlap + phrase match + relationship/story salience; stable ties."""
    words = set(w.lower() for w in WORD.findall(query) if len(w) >= 3)
    scored = []
    for index, item in enumerate(memories):
        content = item.content.strip()
        terms = set(w.lower() for w in WORD.findall(content) if len(w) >= 3)
        match = len(words & terms)
        if not match:
            continue
        phrase = int(bool(query.strip()) and query.strip().lower() in content.lower())
        category = getattr(item, 'category', '')
        bonus = 1 if category in ('relationship', 'story') else 0
        scored.append((match * 4 + phrase * 3 + bonus, -index, item))
    scored.sort(key=lambda x: (-x[0], -x[1]))
    return [item for _, _, item in scored[:limit]]


def repetition_score(reply: str, prior_replies: list[str]) -> float:
    norm = ' '.join(reply.lower().split())[:1400]
    if not norm or not prior_replies:
        return 0.0
    return max(SequenceMatcher(None, norm, ' '.join(p.lower().split())[:1400]).ratio()
               for p in prior_replies[-5:] if p.strip()) if any(p.strip() for p in prior_replies) else 0.0


def consistency_instruction(character_name: str, group: bool) -> str:
    instruction = (f'Character consistency: respond only as {character_name}. Preserve established '
                   'personality, voice, viewpoint, and continuity. Do not invent remembered facts. '
                   'Avoid repeating wording or complete actions from recent turns; advance the scene naturally. '
                   'Never control the user persona or decide their actions.')
    if group:
        instruction += (' Group coordination: respond as the selected speaker only. '
                        'Do not write dialogue for other characters. Respect each speaker’s previous statements.')
    return instruction


def quality_evaluation(reply: str, earlier: list[str], character_name: str) -> dict:
    overlap = repetition_score(reply, earlier)
    return {'repetition_similarity': round(overlap, 3), 'possibly_repetitive': overlap >= 0.88,
            'empty': not bool(reply.strip()), 'character': character_name,
            'estimated_output_tokens': estimated_tokens(reply)}
