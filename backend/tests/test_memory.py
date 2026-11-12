from types import SimpleNamespace
from app.services.memory import parse_extracted, relevant_memories, lore_matches


def test_extractor_rejects_invalid_or_excessive_content():
    assert parse_extracted('not json') == []
    assert parse_extracted('{"category":"fact"}') == []
    assert parse_extracted('[{"category":"secret","content":"unknown thing"}]') == []
    assert parse_extracted('[{"category":"fact","content":"x"}]') == []
    assert parse_extracted('[{"category":"fact","content":"Enjoys stargazing."}]') == [
        {"category": "fact", "content": "Enjoys stargazing."}]


def test_recall_only_matches_relevant_terms():
    memories = [SimpleNamespace(content='Lives in a mountain cabin'), SimpleNamespace(content='Prefers tea to coffee')]
    assert [m.content for m in relevant_memories(memories, 'Would you like tea?')] == ['Prefers tea to coffee']
    assert relevant_memories(memories, 'New unrelated message') == []


def test_lorebook_keywords():
    entries = [SimpleNamespace(keywords='dragon castle'), SimpleNamespace(keywords='forest river')]
    assert lore_matches(entries, 'The dragon flies') == entries[:1]
    assert lore_matches(entries, 'hello') == []
