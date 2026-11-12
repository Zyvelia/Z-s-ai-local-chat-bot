"""v1.6 deterministic inference quality and budget tests (no model downloads)."""
from pathlib import Path
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from app.services.quality import (
    estimated_tokens, clip_tokens, assemble_context, rank_memories,
    repetition_score, consistency_instruction, quality_evaluation,
)


def test_estimator_and_clipping_handle_unicode():
    assert estimated_tokens('') == 0
    assert estimated_tokens('Hello world') > 0
    assert estimated_tokens('你好世界' * 200) > 200
    assert estimated_tokens(clip_tokens('你好世界' * 100, 20)) <= 22
    assert clip_tokens('word' * 20, 0) == ''


def test_budget_keeps_latest_and_reserves_output():
    history = ([{'role': 'user', 'content': f'previous message {i} ' * 90} for i in range(35)]
               + [{'role': 'user', 'content': 'The gate is opening now'}])
    plan = assemble_context([('identity', 'Act as Nova. ' * 130),
                             ('story', 'Kingdom setting ' * 400),
                             ('notes', 'Private details ' * 300)], history,
                            num_ctx=2048, output_tokens=512)
    diag = plan.diagnostics
    assert diag['reserved_output_and_headroom'] >= 512
    assert diag['estimated_input_tokens'] <= diag['input_budget'] + 5
    assert diag['history_messages_skipped'] > 0
    assert any('gate is opening' in m['content'] for m in plan.messages)
    assert diag['sections'][1]['truncated']
    assert not any('previous message 0' in m['content'] for m in plan.messages)


def test_short_context_still_preserves_system_and_latest():
    plan = assemble_context([('identity', 'You are Nova' * 1000)],
                            [{'role': 'user', 'content': 'Please respond now'}],
                            num_ctx=512, output_tokens=2048)
    assert plan.messages[0]['role'] == 'system'
    assert plan.messages[-1]['role'] == 'user'
    assert plan.diagnostics['estimated_input_tokens'] <= plan.diagnostics['input_budget'] + 5


def test_prioritized_memory_ranking_is_stable_and_scoped_to_input():
    rows = [SimpleNamespace(content='The old harbor is quiet', category='fact'),
            SimpleNamespace(content='Nova trusts the harbor guard', category='relationship'),
            SimpleNamespace(content='The harbor closes at dusk', category='story'),
            SimpleNamespace(content='Likes spicy noodles', category='preference')]
    result = rank_memories(rows, 'harbor guard', limit=2)
    assert result[0] is rows[1]
    assert len(result) == 2
    assert rows[3] not in result
    assert rank_memories(rows, 'unrelated', limit=4) == []


def test_repetition_evaluation_and_consistency():
    text = 'The storm approaches. We need shelter.'
    assert repetition_score(text, [text]) == pytest.approx(1)
    assert repetition_score(text, []) == 0
    q = quality_evaluation(text, [text], 'Nova')
    assert q['possibly_repetitive'] is True
    assert quality_evaluation('New dialogue', [text], 'Nova')['empty'] is False
    assert 'selected speaker only' in consistency_instruction('Nova', True)
    assert 'selected speaker only' not in consistency_instruction('Nova', False)


def test_no_new_database_migration_required():
    root = Path(__file__).resolve().parents[1]
    assert (root / 'migrations/012_story_engine.sql').exists()
    code = (root / 'app/api/routes.py').read_text()
    assert 'assemble_context(sections, history_messages' in code
    assert 'quality_evaluation(full_reply' in code
    assert '/prompt-diagnostics' in code
    assert 'rank_memories(learned, prompt_text)' in code
