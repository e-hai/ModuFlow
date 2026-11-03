"""
Lead intake dialogue before a strategic initiative is created.

Lead records what the human said and leaves a draft they can edit.
Market and competitor figures are not filled in here.
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


_BUDGET_RE = re.compile(
    r"[\$￥]?\s*([0-9]{1,3}(?:,[0-9]{3})+|[0-9]+(?:\.[0-9]+)?)\s*(万|k|美元|刀|usd|元)?",
    re.I,
)


def _extract_budget(text: str) -> Optional[float]:
    """A budget the human actually wrote, such as 15,000 美元 or $10k."""
    match = _BUDGET_RE.search(text or "")
    if not match:
        return None
    try:
        value = float(match.group(1).replace(",", ""))
    except ValueError:
        return None
    unit = (match.group(2) or "").lower()
    if unit == "万":
        value *= 10000
    elif unit == "k":
        value *= 1000
    if 100 <= value <= 10000000:
        return value
    return None


def _name_from_words(text: str) -> str:
    cleaned = re.sub(r"[，,。；;]?\s*(?:前期)?总?预算[^。；\n]*", "", text or "")
    cleaned = _BUDGET_RE.sub("", cleaned)
    cleaned = cleaned.strip(" ，,。;；")
    return (cleaned[:40] or "未命名战略工程")


def _missing(draft: Dict[str, Any]) -> List[str]:
    labels = [
        ("name", "工程名称"),
        ("target_market", "目标市场"),
        ("business_model_hypothesis", "商业模式假设"),
        ("budget", "预算"),
    ]
    return [label for key, label in labels if not draft.get(key)]


async def intake_lead_dialogue(
    messages: List[Dict[str, str]],
    current_draft: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Record the human's words into an editable draft. Do not invent a track dossier."""
    if not messages:
        return {
            "reply": (
                "我是项目总控 Lead。\n\n"
                "立项前先把方向谈清楚。请用你自己的话说明：做什么、卖给谁、打算怎么收费、准备投多少。\n\n"
                "我只把你说的内容整理进右侧草案。标成已观测的市场和竞品内容，只来自可靠来源打开的摘录。"
            ),
            "proposal": current_draft or {},
            "quick_prompts": [
                "这个工程准备做什么？",
                "目标市场是哪里？",
                "准备怎么收费？",
                "总预算是多少？",
            ],
        }

    user_inputs = [m["content"] for m in messages if m.get("role") == "user" and m.get("content")]
    last_user_message = user_inputs[-1] if user_inputs else ""
    full_context = "\n".join(user_inputs)
    draft = dict(current_draft or {})

    if last_user_message and not draft.get("strategic_intent"):
        draft["strategic_intent"] = last_user_message.strip()
    if full_context and not draft.get("description"):
        draft["description"] = full_context.strip()
    if not draft.get("name"):
        draft["name"] = _name_from_words(last_user_message or full_context)

    stated_budget = _extract_budget(last_user_message) or _extract_budget(full_context)
    if stated_budget is not None:
        draft["suggested_budget"] = float(stated_budget)
        draft["budget"] = float(stated_budget)
        draft["hard_stop_loss"] = float(stated_budget * 1.3)
        draft["currency"] = draft.get("currency") or "USD"

    missing = _missing(draft)
    heard = draft.get("strategic_intent") or last_user_message or "（还没有）"
    lines = [
        "我是项目总控 Lead。右侧草案只保留你已经说清楚的内容。",
        f"已记下：{heard}",
    ]
    if draft.get("budget"):
        lines.append(
            f"预算按你写的金额记为 ${draft['budget']:,.0f} {draft.get('currency') or 'USD'}，"
            f"硬止损先按 1.3 倍记为 ${draft.get('hard_stop_loss', 0):,.0f}。你可以改。"
        )
    if missing:
        lines.append("还需要你定：" + "、".join(missing) + "。")
    else:
        lines.append("名称、市场、收费假设和预算都已有内容。请在右侧改完再采纳。")
    lines.append("标成已观测的内容必须来自可靠来源的摘录。确认后点「采纳 Lead 提案并正式创建战略工程」。")

    prompts = []
    if not draft.get("target_market"):
        prompts.append("目标市场是")
    if not draft.get("business_model_hypothesis"):
        prompts.append("收费方式是")
    if not draft.get("budget"):
        prompts.append("总预算是")
    if not prompts:
        prompts = ["名称改成", "硬止损改成"]

    return {
        "reply": "\n".join(lines),
        "proposal": draft,
        "quick_prompts": prompts,
    }


def _signals_from_index(index: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    signals = []
    for row in index:
        url = row.get("url") or ""
        quote = row.get("quote") or ""
        if not url or not quote:
            continue
        signals.append({
            "type": row.get("kind") or "source",
            "claim": quote,
            "status": "已观测",
            "source": url,
        })
    return signals


def _apply_citations(draft: Dict[str, Any], workspace: Path) -> Dict[str, Any]:
    from backend.app.services.reliable_sources import UNVERIFIED, cite

    cited = cite(draft.get("signals") or [], workspace)
    draft["signals"] = [item for item in cited if item.get("status") != UNVERIFIED]
    assumptions = list(draft.get("unverified_assumptions") or [])
    for item in cited:
        if item.get("status") == UNVERIFIED and item.get("claim"):
            assumptions.append({"claim": item["claim"], "validation_stage": "待验证"})
    draft["unverified_assumptions"] = assumptions
    return draft


async def compose_intake_turn(
    messages: List[Dict[str, str]],
    current_draft: Optional[Dict[str, Any]],
    workspace: Path,
    *,
    catalog: Optional[List[Dict[str, Any]]] = None,
    search=None,
    fetch=None,
) -> Dict[str, Any]:
    """先查阅，再只根据摘录整理草案，最后核对。"""
    from backend.app.services.reliable_sources import lookup_reliable_sources, mount_lookup_tool

    mount_lookup_tool(workspace)
    user_text = "\n".join(
        m.get("content") or "" for m in messages if m.get("role") == "user" and m.get("content")
    )
    looked = lookup_reliable_sources(
        user_text, workspace, catalog=catalog, search=search, fetch=fetch,
    )
    word = await intake_lead_dialogue(messages, current_draft)
    draft = dict(word["proposal"])
    draft["signals"] = list((current_draft or {}).get("signals") or []) + _signals_from_index(looked["index"])
    draft["unverified_assumptions"] = list((current_draft or {}).get("unverified_assumptions") or [])
    draft = _apply_citations(draft, workspace)
    lines = [word["reply"]]
    quotes = [row.get("quote") or "" for row in looked["index"][:5] if row.get("quote")]
    if quotes:
        lines.append("这一轮打开的摘录：")
        lines.extend(f"- {quote}" for quote in quotes)
    else:
        lines.append("这一轮没有打开到可引用的正文。没有摘录的说法保持待验证。")
    return {
        "reply": "\n".join(lines),
        "proposal": draft,
        "quick_prompts": word["quick_prompts"],
    }


def save_intake_request(workspace: Path, messages: List[Dict[str, str]], current_draft: Optional[Dict[str, Any]]) -> None:
    (workspace / "request.json").write_text(json.dumps({
        "messages": messages,
        "current_draft": current_draft or {},
    }, ensure_ascii=False), encoding="utf-8")


def load_intake_result(workspace: Path) -> Optional[Dict[str, Any]]:
    path = workspace / "result.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


async def _cli_comment(workspace: Path, question: str) -> str:
    """harness 只根据已写好的摘录说话。二进制不在或执行失败时返回空字符串。"""
    import asyncio

    from backend.app.adapters.cli_adapter import build_cli_arguments, find_cli_binary
    from backend.app.core.config import settings

    binary = find_cli_binary(settings.AGENT_CLI_COMMAND)
    if not binary:
        return ""
    prompt = (
        "你是项目总控 Lead，正在战略创建阶段和人讨论。\n"
        "只根据本工作区 sources/ 里的摘录分析。没有摘录的数字标成待验证。\n"
        "可以调用工具 lookup_reliable_sources。不要创建战略工程，不要改授权包。\n"
        f"人刚刚说：{question}\n"
    )
    (workspace / "harness_prompt.md").write_text(prompt, encoding="utf-8")
    args = build_cli_arguments(binary, prompt, settings.AGENT_CLI_MODEL)
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            cwd=str(workspace),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, _err = await asyncio.wait_for(proc.communicate(), timeout=180)
    except Exception:
        return ""
    return (out or b"").decode("utf-8", "replace").strip()


async def run_intake_discuss(db, draft_id: str, *, use_cli: bool = True, search=None, fetch=None) -> Dict[str, Any]:
    """执行器任务。查阅可靠来源，整理草案，再核对。"""
    from backend.app.services.reliable_sources import intake_workspace

    workspace = intake_workspace(draft_id)
    raw = json.loads((workspace / "request.json").read_text(encoding="utf-8"))
    messages = raw.get("messages") or []
    current_draft = raw.get("current_draft") or {}
    result = await compose_intake_turn(messages, current_draft, workspace, search=search, fetch=fetch)
    if use_cli:
        question = "\n".join(m.get("content") or "" for m in messages if m.get("role") == "user")
        comment = await _cli_comment(workspace, question)
        if comment:
            result["reply"] = result["reply"] + "\n\n" + comment
    (workspace / "result.json").write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    return {"status": "done", "draft_id": draft_id}

