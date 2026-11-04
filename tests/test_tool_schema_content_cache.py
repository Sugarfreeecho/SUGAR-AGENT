"""Exact schema counts survive rebuilt containers, with bounded owned storage."""
from concurrent.futures import ThreadPoolExecutor
import copy
import threading
from types import SimpleNamespace

import pytest


@pytest.fixture
def counts(monkeypatch):
    import agent_tokenizer as tokens

    calls=[]
    def count(raw):
        calls.append(raw)
        return len(raw.encode('utf-8'))
    monkeypatch.setattr(tokens,'count_text_tokens',count)
    monkeypatch.setattr(tokens,'_TOOL_SCHEMA_CACHE',__import__('collections').OrderedDict())
    if hasattr(tokens,'_TOOL_SCHEMA_CONTENT_CACHE'):
        monkeypatch.setattr(tokens,'_TOOL_SCHEMA_CONTENT_CACHE',__import__('collections').OrderedDict())
        monkeypatch.setattr(tokens,'_TOOL_SCHEMA_CONTENT_CACHE_BYTES',0)
        monkeypatch.setattr(tokens,'_TOOL_SCHEMA_CACHE_STATE',None)
    return tokens,calls


def schemas(description='查找文件'):
    return [{'type':'function','function':{'name':'find','description':description,
        'parameters':{'type':'object','properties':{'path':{'type':'string'}}}}}]


def test_rebuilt_lists_reuse_exact_count_without_retaining_caller_mutations(counts):
    tokens,calls=counts
    first=schemas()
    expected=tokens.count_tool_definition_tokens(first)
    assert tokens.count_tool_definition_tokens(copy.deepcopy(first))==expected
    assert len(calls)==1
    replacement=schemas('new description')
    assert tokens.count_tool_definition_tokens(replacement)!=expected
    replacement[0]['function']['description']='not a published input'
    assert tokens.count_tool_definition_tokens(schemas('new description'))==len(calls[-1].encode('utf-8'))
    assert len(calls)==2


def test_same_count_cache_does_not_cross_tool_filter_or_alias_changes(counts):
    tokens,calls=counts
    both=[*schemas(),*schemas('another')]
    both[1]['function']['name']='second'
    first=tokens.count_tool_definition_tokens(both)
    renamed=copy.deepcopy(both)
    renamed[0]['function']['name']='renamed'
    assert tokens.count_tool_definition_tokens(renamed)!=first
    assert tokens.count_tool_definition_tokens(both[:1])!=first
    assert len(calls)==3


def test_concurrent_identical_schema_counts_are_single_flight(counts,monkeypatch):
    tokens,calls=counts
    entered,release=threading.Event(),threading.Event()
    original=tokens.count_text_tokens
    def slow(raw):
        entered.set()
        assert release.wait(3)
        return original(raw)
    monkeypatch.setattr(tokens,'count_text_tokens',slow)
    with ThreadPoolExecutor(8) as pool:
        futures=[pool.submit(tokens.count_tool_definition_tokens,schemas()) for _ in range(8)]
        try:
            assert entered.wait(2)
        finally:
            release.set()
        results=[future.result(3) for future in futures]
    assert len(set(results))==1
    assert len(calls)==1


def test_cache_is_bounded_by_bytes_and_skips_oversized_schemas(counts,monkeypatch):
    tokens,calls=counts
    monkeypatch.setattr(tokens,'_TOOL_SCHEMA_CONTENT_CACHE_MAX_BYTES',600,raising=False)
    for i in range(20):
        tokens.count_tool_definition_tokens(schemas(str(i)*50))
    assert tokens._TOOL_SCHEMA_CONTENT_CACHE_BYTES<=600
    assert sum(len(raw.encode('utf-8')) for raw in tokens._TOOL_SCHEMA_CONTENT_CACHE)<=600
    big=schemas('x'*1000)
    expected=tokens.count_tool_definition_tokens(big)
    assert tokens.count_tool_definition_tokens(copy.deepcopy(big))==expected
    assert len(calls)==22


def test_tokenizer_or_counter_change_invalidates_identity_and_content_counts(counts,monkeypatch):
    tokens,_=counts
    first=schemas()
    tokens.count_tool_definition_tokens(first)
    monkeypatch.setattr(tokens,'count_text_tokens',lambda _:17)
    assert tokens.count_tool_definition_tokens(first)==17
    monkeypatch.setattr(tokens,'_TOKENIZER',object())
    monkeypatch.setattr(tokens,'count_text_tokens',lambda _:19)
    assert tokens.count_tool_definition_tokens(schemas())==19


def test_transient_encode_failure_is_retried_for_same_and_rebuilt_schema(monkeypatch):
    import agent_tokenizer as tokens

    class Tokenizer:
        failures=1
        def encode(self,raw):
            if self.failures:
                self.failures-=1
                raise ValueError('transient encode failure')
            return SimpleNamespace(ids=[0]*7)
    tokenizer=Tokenizer()
    monkeypatch.setattr(tokens,'_TOKENIZER',tokenizer)
    monkeypatch.setattr(tokens,'_LOAD_FAILED',False)
    monkeypatch.setattr(tokens,'_get_tokenizer',lambda:tokenizer)
    first=schemas()
    assert tokens.count_tool_definition_tokens(first)!=7
    assert tokens.count_tool_definition_tokens(first)==7
    assert tokens.count_tool_definition_tokens(schemas())==7
