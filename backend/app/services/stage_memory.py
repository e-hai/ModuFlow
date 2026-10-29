"""Product-owned stage progress. Every harness reads this; CLI sessions are not resumed."""

from datetime import datetime
from typing import Any, Dict, List, Optional

DRAFT_EMBED_LIMIT = 12_000
DRAFT_SUMMARY_CHARS = 400
MAX_PENDING_NOTES = 5
ISSUE_SUMMARY_CHARS = 300


def deliverable_filename(module_code: str, module_name: str) -> str:
    return f"交付物_{module_code}_{module_name}.md"


def issue_summary_text(description: Any) -> str:
    if isinstance(description, dict):
        text = str(description.get("summary") or description.get("expected") or "")
    else:
        text = str(description or "")
    return text.strip()[:ISSUE_SUMMARY_CHARS]


def pending_revision_notes(
    messages: List[Dict[str, Any]],
    *,
    draft_created_at: Optional[datetime],
    current_instruction: str,
    limit: int = MAX_PENDING_NOTES,
) -> List[str]:
    """Feedback written after the latest draft, excluding the instruction already shown below."""
    current = (current_instruction or "").strip()
    kept: List[str] = []
    for msg in messages:
        if msg.get("message_type") != "feedback":
            continue
        created = msg.get("created_at")
        if draft_created_at is not None and created is not None and created <= draft_created_at:
            continue
        content = str(msg.get("content") or "").strip()
        if not content or content == current:
            continue
        kept.append(content)
    return kept[-limit:]


def render_stage_progress(
    *,
    filename: str,
    draft_version: Optional[int],
    draft_content: Optional[str],
    issues: List[Dict[str, Any]],
    pending_notes: List[str],
    current_instruction: str = "",
) -> str:
    """One section a new CLI can continue from. Closed issues and the current instruction stay out."""
    lines = ["## 本工序进度", ""]
    text = (draft_content or "").strip()
    version = draft_version or 1
    if not text:
        lines.append("本工序还没有稿。")
    elif len(text) > DRAFT_EMBED_LIMIT:
        lines.append(
            f"当前稿是 `{filename}`，版本 V{version}。"
            f"正文有 {len(text)} 字，请在当前目录修改这个文件，不要另起一份。"
        )
        lines.append("")
        lines.append("开头摘要：")
        lines.append(text[:DRAFT_SUMMARY_CHARS])
    else:
        lines.append(
            f"当前稿是 `{filename}`，版本 V{version}。在这个文件上改，没被点名的段落保持原样。"
        )
        lines.append("")
        lines.append("```markdown")
        lines.append(text)
        lines.append("```")

    open_issues = [item for item in issues if (item.get("status") or "open") != "closed"]
    lines.append("")
    if open_issues:
        lines.append("未关闭事项：")
        for item in open_issues:
            summary = (item.get("summary") or "").strip() or "无补充说明"
            lines.append(
                f"- [{item.get('category') or '问题'} / {item.get('severity') or '未分级'}] "
                f"{item.get('title') or '未命名'}：{summary}"
            )
    else:
        lines.append("未关闭事项：没有。")

    current = (current_instruction or "").strip()
    notes = [note.strip() for note in pending_notes if note and note.strip() and note.strip() != current]
    if notes:
        lines.append("")
        lines.append("尚未写进稿子的修改意见：")
        for note in notes[-MAX_PENDING_NOTES:]:
            lines.append(f"- {note}")
    return "\n".join(lines)
