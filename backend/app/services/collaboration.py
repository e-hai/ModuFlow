"""
工序协作评审与交接。

协作角色不再只是挂载工具：主责交付物通过确定性检查后，先过协作角色的交叉检查与关键评审，
再提交关口。评审只能要求修订或提出 CR，不能放行关口。
"""
import re
from typing import Any, Dict, List, Optional

from backend.app.core.config import settings
from backend.app.services.deliverable_audit import (
    audit_unit_economics,
    iter_json_objects,
    merged_fields,
    _number,
)

VERDICTS = ("approve", "request_changes", "raise_cr")
REVIEW_MESSAGE_TYPE = "review"
REVIEW_TEXT_LIMIT = 20000

# kind: "check" = deterministic cross-check in this module; "llm" = the collaborator Agent reviews.
REVIEW_MATRIX: Dict[str, List[Dict[str, Any]]] = {
    "04": [
        {"reviewer": "ba", "kind": "check", "check": "fakedoor_budget",
         "focus": "外测预算不超过授权包工序 04 额度"},
    ],
    "05": [
        {"reviewer": "eng", "kind": "llm",
         "focus": "技术可行性：每个模块的业务规则能否在现有技术栈与 Profile 约束下实现；不可行项必须指出并建议走 CR"},
        {"reviewer": "ux", "kind": "llm",
         "focus": "交互完整性：每个视图是否有 Default/Loading/Empty/Error 四态与异常分支，文案是否可落地"},
    ],
    "06": [
        {"reviewer": "pm", "kind": "check", "check": "view_coverage",
         "focus": "工序 05 视图索引全部有设计规范"},
    ],
    "07": [
        {"reviewer": "qa", "kind": "check", "check": "acceptance_coverage",
         "focus": "工序 05 验收编号全部有对应测试"},
        {"reviewer": "qa", "kind": "llm",
         "focus": "可测试性：核心逻辑是否可被自动化测试覆盖，单测报告与 AC 是否对得上"},
    ],
    "09": [
        {"reviewer": "eng", "kind": "llm",
         "focus": "回滚与 Remote Config 降级方案在工程上能否真正执行（开关位置、回滚步骤、数据兼容）"},
    ],
    "10": [
        {"reviewer": "ba", "kind": "check", "check": "ecac_vs_ltv",
         "focus": "eCAC 熔断线不突破工序 02 的 LTV/CAC ≥ 3"},
    ],
    "11": [
        {"reviewer": "pm", "kind": "check", "check": "backlog_evidence",
         "focus": "Backlog 每一项都有留存或流失数据依据"},
    ],
}

# Anchors a stage needs from upstream baselines before lead dispatches it.
HANDOFF_REQUIREMENTS: Dict[str, List[Dict[str, str]]] = {
    "06": [
        {"upstream": "05", "anchor": "视图索引 V-xx", "pattern": r"V-\d{2}"},
        {"upstream": "05", "anchor": "埋点字典", "pattern": r"埋点"},
    ],
    "07": [
        {"upstream": "05", "anchor": "验收编号 AC-xx", "pattern": r"AC-\d{2}"},
        {"upstream": "06", "anchor": "Design Tokens", "pattern": r"(?i)design[ _]?tokens"},
    ],
    "08": [
        {"upstream": "05", "anchor": "验收编号 AC-xx", "pattern": r"AC-\d{2}"},
        {"upstream": "07", "anchor": "单测覆盖率 coverage_percent", "pattern": r"coverage_percent"},
    ],
    "09": [
        {"upstream": "08", "anchor": "缺陷清零记录 open_p0/open_p1", "pattern": r"open_p0"},
    ],
    "10": [
        {"upstream": "02", "anchor": "变现阶梯", "pattern": r"变现阶梯|订阅|买断"},
        {"upstream": "09", "anchor": "发布与回滚计划", "pattern": r"回滚|灰度|rollback"},
    ],
    "11": [
        {"upstream": "05", "anchor": "埋点字典", "pattern": r"埋点"},
    ],
}


def review_mode() -> str:
    mode = (getattr(settings, "COLLAB_REVIEW_MODE", "full") or "full").lower()
    return mode if mode in ("full", "deterministic", "off") else "full"


def reviews_for_stage(module_code: str) -> List[Dict[str, Any]]:
    mode = review_mode()
    if mode == "off":
        return []
    specs = REVIEW_MATRIX.get(str(module_code), [])
    if mode == "deterministic":
        specs = [s for s in specs if s["kind"] == "check"]
    return specs


def _result(spec: Dict[str, Any], verdict: str, findings: List[str], **extra: Any) -> Dict[str, Any]:
    return {"reviewer": spec["reviewer"], "kind": spec["kind"], "focus": spec["focus"],
            "verdict": verdict, "findings": findings, **extra}


# ---------------------------------------------------------------------------
# ID extraction with range expansion (V-01~V-04)
# ---------------------------------------------------------------------------

def extract_ids(prefix: str, text: str) -> List[str]:
    ids: List[str] = []
    pattern = re.compile(rf"{prefix}-(\d{{2}})(?:\s*[~～至]\s*(?:{prefix}-)?(\d{{2}}))?")
    for match in pattern.finditer(text or ""):
        start = int(match.group(1))
        end = int(match.group(2)) if match.group(2) else start
        if end < start or end - start > 50:
            end = start
        for n in range(start, end + 1):
            tag = f"{prefix}-{n:02d}"
            if tag not in ids:
                ids.append(tag)
    return ids


# ---------------------------------------------------------------------------
# Deterministic cross-checks
# ---------------------------------------------------------------------------

def _stage_limit(auth_data: Optional[Dict[str, Any]], stage: str) -> Optional[float]:
    if not auth_data:
        return None
    for section, key in (("financial_budget", "per_stage_limits"), ("budget", "stage_allocations")):
        table = (auth_data.get(section) or {}).get(key) or {}
        if stage in table:
            try:
                return float(table[stage])
            except (TypeError, ValueError):
                return None
    return None


def check_fakedoor_budget(spec, texts, upstream, auth_data) -> Dict[str, Any]:
    budget = _number(merged_fields(texts), "test_budget_usd")
    if budget is None:
        return _result(spec, "request_changes", ["交付物缺少结构化字段 test_budget_usd（外测总预算，USD）"])
    limit = _stage_limit(auth_data, "04")
    if limit is None:
        return _result(spec, "approve", [f"授权包未设工序 04 额度，外测预算 ${budget:g} 仅记录"])
    if budget > limit:
        return _result(spec, "request_changes", [f"外测预算 ${budget:g} 超过授权包工序 04 额度 ${limit:g}"])
    return _result(spec, "approve", [f"外测预算 ${budget:g} ≤ 工序 04 额度 ${limit:g}"])


def _coverage(spec, texts, upstream_text: Optional[str], prefix: str, label: str) -> Dict[str, Any]:
    if not upstream_text:
        return _result(spec, "approve", [f"本迭代没有工序 05 基线，跳过{label}覆盖检查"])
    required = extract_ids(prefix, upstream_text)
    if not required:
        return _result(spec, "approve", [f"工序 05 基线没有 {prefix}-xx 编号"])
    present = set(extract_ids(prefix, "\n".join(texts)))
    missing = [i for i in required if i not in present]
    if missing:
        return _result(spec, "request_changes", [f"未覆盖工序 05 的{label}: {', '.join(missing)}"])
    return _result(spec, "approve", [f"已覆盖工序 05 全部{label} ({len(required)} 项)"])


def check_view_coverage(spec, texts, upstream, auth_data) -> Dict[str, Any]:
    return _coverage(spec, texts, upstream.get("05"), "V", "视图")


def check_acceptance_coverage(spec, texts, upstream, auth_data) -> Dict[str, Any]:
    return _coverage(spec, texts, upstream.get("05"), "AC", "验收用例")


def check_ecac_vs_ltv(spec, texts, upstream, auth_data) -> Dict[str, Any]:
    limit = _number(merged_fields(texts), "ecac_limit_usd")
    if limit is None:
        return _result(spec, "request_changes", ["交付物缺少 ecac_limit_usd"])
    if not upstream.get("02"):
        return _result(spec, "approve", ["本迭代没有工序 02 基线，跳过 LTV 对照"])
    ue = audit_unit_economics([upstream["02"]])
    ltv = ue.get("ltv_180d_usd")
    if not ltv:
        return _result(spec, "approve", ["工序 02 基线没有可复核的 LTV"])
    ceiling = round(float(ltv) / 3.0, 3)
    if limit > ceiling:
        return _result(spec, "request_changes", [
            f"eCAC 熔断线 ${limit:g} 高于 LTV ${ltv:g} / 3 = ${ceiling:g}，到线时 LTV/CAC 低于 3，"
            "须下调熔断线或由 ba 在工序 02 重新测算"
        ])
    return _result(spec, "approve", [f"eCAC 熔断线 ${limit:g} ≤ LTV/3 = ${ceiling:g}"])


_EVIDENCE_PATTERN = re.compile(r"D1|D7|D30|留存|流失|转化|\d+(?:\.\d+)?\s?%", flags=re.I)
_BACKLOG_ROW = re.compile(r"^\|\s*P[0-3]\s*\|")


def check_backlog_evidence(spec, texts, upstream, auth_data) -> Dict[str, Any]:
    rows = [line.strip() for text in texts for line in (text or "").splitlines() if _BACKLOG_ROW.match(line.strip())]
    if not rows:
        return _result(spec, "request_changes", ["没有找到 Backlog 表格行（| P1 | 需求 | 数据依据 |）"])
    weak = [row for row in rows if not _EVIDENCE_PATTERN.search(row)]
    if weak:
        return _result(spec, "request_changes", [f"Backlog 项缺少留存/流失数据依据: {row[:80]}" for row in weak[:5]])
    return _result(spec, "approve", [f"{len(rows)} 项 Backlog 均有数据依据"])


CHECKS = {
    "fakedoor_budget": check_fakedoor_budget,
    "view_coverage": check_view_coverage,
    "acceptance_coverage": check_acceptance_coverage,
    "ecac_vs_ltv": check_ecac_vs_ltv,
    "backlog_evidence": check_backlog_evidence,
}


def run_check(spec, texts, upstream, auth_data) -> Dict[str, Any]:
    return CHECKS[spec["check"]](spec, texts, upstream, auth_data)


# ---------------------------------------------------------------------------
# LLM review prompt and verdict parsing
# ---------------------------------------------------------------------------

def build_review_instruction(spec: Dict[str, Any], module_code: str, module_name: str, content: str) -> str:
    body = content if len(content) <= REVIEW_TEXT_LIMIT else content[:REVIEW_TEXT_LIMIT] + "\n…（已截断）"
    return (
        f"【协作评审】你以 {spec['reviewer']} 的身份评审工序 {module_code}「{module_name}」主责角色的交付物。\n"
        f"评审重点：{spec['focus']}\n"
        "规则：只评审、不改文件；不能放行关口；只就你的专业边界提意见。\n"
        "若问题出在上游基线（例如 PRD 本身不可行），用 raise_cr 并写明 cr_target_stage；"
        "若 CR 涉及支付、隐私、用户数据或加密，在 cr_flags 里置 is_payment_related / is_privacy_related / "
        "is_user_data_related / is_encryption_related 为 true。\n"
        "输出末尾必须附一个 ```json 代码块：\n"
        '{"verdict": "approve | request_changes | raise_cr", "findings": ["..."], '
        '"cr_target_stage": "05", "cr_flags": {}}\n\n'
        f"【待评审交付物】\n{body}"
    )


def parse_verdict(text: str) -> Dict[str, Any]:
    """Unparseable output counts as request_changes: a review that can't be read can't clear a stage."""
    parsed = None
    for obj in iter_json_objects(text or ""):
        if "verdict" in obj:
            parsed = obj
    if not parsed or str(parsed.get("verdict")).strip() not in VERDICTS:
        return {"verdict": "request_changes", "findings": ["评审输出缺少可解析的 verdict JSON，按需修订处理"],
                "parse_error": True}
    findings = parsed.get("findings") or []
    if not isinstance(findings, list):
        findings = [str(findings)]
    flags = parsed.get("cr_flags") if isinstance(parsed.get("cr_flags"), dict) else {}
    return {
        "verdict": str(parsed["verdict"]).strip(),
        "findings": [str(f) for f in findings][:10],
        "cr_target_stage": str(parsed.get("cr_target_stage") or "05"),
        "cr_flags": {k: bool(v) for k, v in flags.items()},
    }


def simulated_review(spec: Dict[str, Any], module_code: str) -> str:
    return (
        f"演示评审（{spec['reviewer']}）：已按「{spec['focus']}」检查工序 {module_code} 交付物，未发现阻断项。\n"
        "```json\n"
        '{"verdict": "approve", "findings": ["演示评审：未发现阻断项"]}\n'
        "```\n"
    )


# ---------------------------------------------------------------------------
# Handoff
# ---------------------------------------------------------------------------

def check_handoff(module_code: str, upstream: Dict[str, str], run_stage_codes: List[str]) -> List[Dict[str, str]]:
    """Missing anchors; upstream stages absent from this run (e.g. hotfix template) are skipped."""
    missing = []
    for req in HANDOFF_REQUIREMENTS.get(str(module_code), []):
        if req["upstream"] not in run_stage_codes:
            continue
        text = upstream.get(req["upstream"])
        if not text or not re.search(req["pattern"], text):
            missing.append(req)
    return missing


def handoff_anchor_fields(text: str) -> Dict[str, Any]:
    return {k: v for k, v in merged_fields([text]).items() if k != "simulated"}


def summarize_reviews(results: List[Dict[str, Any]]) -> str:
    from backend.app.services.gate_copy import review_note
    return review_note(results)
