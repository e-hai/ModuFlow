"""A new CLI continues from the product record, not from a previous harness session."""

from datetime import datetime, timedelta

from backend.app.adapters.cli_adapter import continuation_preamble, deliverable_write_rule
from backend.app.services.stage_memory import pending_revision_notes, render_stage_progress


def _progress(**overrides):
    data = {
        "filename": "交付物_03_产品方向决策.md",
        "draft_version": 2,
        "draft_content": "是否按这个方向立项：口袋里的自律神经重置器。",
        "issues": [
            {
                "title": "健康与生物识别还没写清",
                "category": "requirement_cr",
                "severity": "major",
                "status": "open",
                "summary": "需求里还没写为什么需要这个权限",
            },
            {
                "title": "已经关掉的竞品表",
                "category": "bug",
                "severity": "minor",
                "status": "closed",
                "summary": "这条不该再出现",
            },
        ],
        "pending_notes": ["【cmp 评审：需修订】补上授权理由"],
        "current_instruction": "请按未关闭事项改一版",
    }
    data.update(overrides)
    return render_stage_progress(**data)


def test_open_issue_and_draft_are_in_the_context_closed_issue_is_not():
    text = _progress()
    assert "口袋里的自律神经重置器" in text
    assert "健康与生物识别还没写清" in text
    assert "需求里还没写为什么需要这个权限" in text
    assert "requirement_cr" in text
    assert "major" in text
    assert "已经关掉的竞品表" not in text
    assert "这条不该再出现" not in text
    assert "请按未关闭事项改一版" not in text
    assert "补上授权理由" in text


def test_stage_without_a_draft_says_so():
    text = _progress(draft_content="  ", draft_version=None, issues=[], pending_notes=[])
    assert "本工序还没有稿" in text
    assert "口袋里的自律神经重置器" not in text
    assert "未关闭事项：没有。" in text


def test_oversized_draft_keeps_the_filename_and_drops_the_tail():
    tail = "TAIL_TOKEN_SHOULD_NOT_APPEAR"
    text = _progress(
        draft_content=("开头这是摘要标记。" + ("x" * 13_000) + tail),
        issues=[],
        pending_notes=[],
    )
    assert "交付物_03_产品方向决策.md" in text
    assert "版本 V2" in text
    assert "请在当前目录修改这个文件" in text
    assert "开头这是摘要标记。" in text
    assert tail not in text
    assert "x" * 13_000 not in text


def test_feedback_already_in_the_draft_is_not_repeated():
    drafted_at = datetime(2026, 10, 29, 10, 0, 0)
    notes = pending_revision_notes(
        [
            {
                "message_type": "feedback",
                "content": "改掉竞品表",
                "created_at": drafted_at - timedelta(minutes=5),
            },
            {
                "message_type": "feedback",
                "content": "补上授权理由",
                "created_at": drafted_at + timedelta(minutes=5),
            },
            {
                "message_type": "feedback",
                "content": "请按未关闭事项改一版",
                "created_at": drafted_at + timedelta(minutes=6),
            },
            {
                "message_type": "instruction",
                "content": "这条不是修改意见",
                "created_at": drafted_at + timedelta(minutes=7),
            },
        ],
        draft_created_at=drafted_at,
        current_instruction="请按未关闭事项改一版",
    )
    assert notes == ["补上授权理由"]


def test_prompt_revises_an_existing_file_and_writes_a_new_one_otherwise():
    name = "交付物_03_产品方向决策.md"
    revise = deliverable_write_rule(name, True)
    fresh = deliverable_write_rule(name, False)
    assert "在现有文件" in revise
    assert "没被点名的段落保持原样" in revise
    assert "不要另起一份新稿" in revise
    assert "一次写入" in fresh
    assert "本工序当前稿" in continuation_preamble(True)
    assert "写交付物" in continuation_preamble(False)
