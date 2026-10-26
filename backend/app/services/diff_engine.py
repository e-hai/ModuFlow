import difflib
from typing import Tuple, List, Optional, Dict, Any

def generate_text_diff(prev_text: Optional[str], new_text: str) -> str:
    """Computes a standard unified diff between two text versions."""
    prev_lines = (prev_text or "").splitlines(keepends=True)
    new_lines = (new_text or "").splitlines(keepends=True)
    diff = difflib.unified_diff(prev_lines, new_lines, fromfile="v_prev", tofile="v_new", n=3)
    return "".join(diff)

def analyze_changes_and_impact(
    module_code: str,
    prev_content: Optional[str],
    new_content: str,
    human_change_summary: Optional[str] = None
) -> Tuple[str, List[str]]:
    """
    Synthesizes a structured change report and identifies affected downstream module codes.
    Returns:
    - diff_summary: Markdown report with Added, Modified, Removed and Human intent
    - impacted_modules: List of module codes, e.g. ["07", "08", "09", "10"]
    """
    diff_text = generate_text_diff(prev_content, new_content)
    
    # 1. Determine affected downstream modules based on module_code & content keywords
    impacted: List[str] = []
    text_lower = (new_content + " " + (human_change_summary or "")).lower()

    if module_code in ("01", "02", "03"):
        impacted = ["04", "05"]
    elif module_code == "04":
        impacted = ["05", "06", "07"]
    elif module_code == "05": # 方向确认与 MVP PRD
        impacted = ["06", "07", "08"]
        if "设计" in text_lower or "ui" in text_lower or "交互" in text_lower or "页面" in text_lower:
            if "06" not in impacted: impacted.append("06")
        if "api" in text_lower or "数据库" in text_lower or "架构" in text_lower or "后端" in text_lower:
            if "07" not in impacted: impacted.append("07")
    elif module_code == "06": # 设计实现
        impacted = ["07", "08"]
    elif module_code == "07": # 开发实现
        impacted = ["08", "09"]
    elif module_code == "08": # 测试与 QA
        impacted = ["09"]
    else:
        impacted = ["11"]

    # 2. Extract structural changes (added, modified, removed)
    added_lines = [l[1:].strip() for l in diff_text.splitlines() if l.startswith("+") and not l.startswith("+++") and len(l.strip()) > 2]
    removed_lines = [l[1:].strip() for l in diff_text.splitlines() if l.startswith("-") and not l.startswith("---") and len(l.strip()) > 2]

    summary_lines = []
    if human_change_summary:
        summary_lines.append(f"### 📝 提交人变更说明\n> {human_change_summary}\n")

    summary_lines.append("### 🔍 差异分析报告")
    if not prev_content:
        summary_lines.append(f"- **初版发布**：创建初始交付物版本，包含全文规范与核心资产。")
    else:
        summary_lines.append(f"- **变更规模**：新增/调整约 {len(added_lines)} 处，移除/替换约 {len(removed_lines)} 处。")
        
        if added_lines:
            sample_added = added_lines[:5]
            summary_lines.append("\n**✨ 关键新增或变更要素：**")
            for item in sample_added:
                summary_lines.append(f"- `{item[:80]}`")
        
        if removed_lines:
            sample_removed = removed_lines[:3]
            summary_lines.append("\n**🗑️ 移除或废弃要素：**")
            for item in sample_removed:
                summary_lines.append(f"- `{item[:80]}`")

    summary_lines.append(f"\n**🎯 关联受影响下游工序**：{', '.join(impacted)}")
    summary_lines.append("下游工序将在本变更审批通过后自动触发【待跟进】警示。")

    return "\n".join(summary_lines), impacted
