"""History rendering must not change live context accounting."""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_context_replay_isolation_runtime():
    result = subprocess.run(['node', str(ROOT/'tests/js/context_replay_isolation_runtime.cjs')],
                            cwd=ROOT, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


def test_provider_usage_cannot_contaminate_local_token_cache(monkeypatch):
    import agent_tokenizer as tokens
    import agent_harness
    from agent_messages import UserMessage, AssistantMessage

    tokens._clear_flatten_token_cache()
    tokens._PROMPT_USAGE_EXACT_CACHE.clear()
    tokens._PROMPT_USAGE_BASELINE_CACHE.clear()
    monkeypatch.setattr(tokens, '_persist_prompt_usage_baseline', lambda *args: None)
    monkeypatch.setattr(tokens, '_load_prompt_usage_baseline', lambda *args: None)
    monkeypatch.setattr(agent_harness, 'strip_reasoning_for_api_request', lambda messages: messages)
    monkeypatch.setattr(tokens, 'count_text_tokens', lambda text: len(text)//4)
    prefix = [UserMessage(content='hello '*100)]
    messages = prefix + [AssistantMessage(content='answer')]
    tools = [{'type':'function','function':{'name':'demo'}}]
    local = tokens.count_message_tokens_incremental(messages)
    tokens.record_prompt_tokens_for_messages('provider', prefix, local*3, tools=tools)
    estimate, source = tokens.estimate_full_input_tokens_for_messages('provider', messages, tools=tools, return_source=True)
    assert source == 'provider_prefix' and estimate > local*2
    assert tokens.count_message_tokens_incremental(messages) == local
    other, other_source = tokens.estimate_full_input_tokens_for_messages('other', messages, tools=tools, return_source=True)
    assert other_source == 'local_estimate'
    assert other == local + tokens.count_tool_definition_tokens(tools)
    assert tokens.message_token_path_stats()['seed'].startswith('text-only:')
