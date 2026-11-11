from session_corpus import strip_think, text_of, ui_row_text


def test_think_blocks_are_stripped_but_code_examples_kept():
    assert strip_think("answer<think>hidden</think>done") == "answerdone"
    assert strip_think("`<think>` stays literal") == "`<think>` stays literal"


def test_block_lists_reduce_to_their_text_blocks():
    assert text_of([{"type": "text", "text": "first"}, {"type": "image", "text": "skip"}]) == "first"


def test_ui_rows_use_one_labelling_rule_for_every_corpus():
    assert ui_row_text({"type": "user", "content": "question"}) == "用户：question"
    assert ui_row_text({"type": "final", "content": "answer<think>x</think>"}) == "助手：answer"
    assert ui_row_text({"type": "final", "content": "answer"}, labelled=False) == "answer"
    assert ui_row_text({"type": "tool_result", "tool": "read_file", "output": "ok"}) == "工具结果（工具=read_file）：ok"


def test_sidebar_search_uses_the_same_text_rules():
    from session_search import _reply, _text

    assert _reply("answer<think>hidden</think>") == "answer"
    assert _text([{"type": "text", "text": "block"}]) == "block"
    assert _text({"unexpected": "dict"}) == ""
