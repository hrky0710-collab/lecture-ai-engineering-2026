"""第3回 演習・宿題のテスト（LLM も API キーも使わない）。

- make_quiz が用語集から問題と答えを作れるか
- save_learning_log が承認待ちで止まり、承認したときだけファイルを作るか
"""

import json

import pytest
from pydantic_ai import DeferredToolRequests
from pydantic_ai.models.test import TestModel

from app import tools
from app.agent import agent


@pytest.fixture
def log_dir(tmp_path, monkeypatch):
    """本物の learning_log/ を汚さないよう、保存先を一時フォルダに差し替える。"""
    monkeypatch.setattr(tools, "LOG_DIR", tmp_path / "learning_log")
    return tools.LOG_DIR


def test_make_quiz_returns_question_and_answer_from_glossary():
    quiz = json.loads(tools.make_quiz(2))
    lecture2 = {e["definition"] for e in tools.load_glossary() if e["lecture"] == 2}
    assert quiz["question"].endswith("の意味は？")
    assert quiz["answer"] in lecture2


def test_make_quiz_unknown_lecture():
    assert "ありません" in tools.make_quiz(0)


def test_save_learning_log_writes_markdown(log_dir):
    message = tools.save_learning_log("第3回 まとめ", "エージェント = モデル + ループ + ツール")
    files = list(log_dir.glob("*.md"))
    assert len(files) == 1 and "保存しました" in message
    assert "モデル + ループ + ツール" in files[0].read_text(encoding="utf-8")


def _run_until_approval(log_dir):
    model = TestModel(call_tools=["save_learning_log"])
    with agent.override(model=model):
        first = agent.run_sync("今日学んだことを記録して")
    # 承認待ちで止まり、まだファイルは作られていない
    assert isinstance(first.output, DeferredToolRequests)
    assert [c.tool_name for c in first.output.approvals] == ["save_learning_log"]
    assert not log_dir.exists() or not list(log_dir.glob("*.md"))
    return model, first


def test_approved_call_saves_file(log_dir):
    model, first = _run_until_approval(log_dir)
    call_id = first.output.approvals[0].tool_call_id
    with agent.override(model=model):
        second = agent.run_sync(
            message_history=first.all_messages(),
            deferred_tool_results=first.output.build_results(approvals={call_id: True}),
        )
    assert isinstance(second.output, str)
    assert len(list(log_dir.glob("*.md"))) == 1


def test_denied_call_does_not_save(log_dir):
    model, first = _run_until_approval(log_dir)
    call_id = first.output.approvals[0].tool_call_id
    with agent.override(model=model):
        second = agent.run_sync(
            message_history=first.all_messages(),
            deferred_tool_results=first.output.build_results(approvals={call_id: False}),
        )
    assert isinstance(second.output, str)
    assert not log_dir.exists() or not list(log_dir.glob("*.md"))
