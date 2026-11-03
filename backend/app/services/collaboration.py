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
    "03": [
        {"reviewer": "ba", "kind": "check", "check": "direction_inherits",
         "focus": "方向卡写上工序 01 的首年盘子，以及工序 02 价格阶梯里的每一档名称"},
    ],
    "04": [
        {"reviewer": "pm", "kind": "check", "check": "direction_carried",
         "focus": "需求规格写上工序 03 的价值主张、必做、明确不做和假设编号"},
        {"reviewer": "eng", "kind": "llm",
         "focus": "技术可行性：每个模块的业务规则能否在现有技术栈与 Profile 约束下实现；不可行项必须指出并建议走 CR"},
        {"reviewer": "ux", "kind": "llm",
         "focus": "交互完整性：每个视图是否有 Default/Loading/Empty/Error 四态与异常分支，文案是否可落地"},
    ],
    "05": [
        {"reviewer": "pm", "kind": "check", "check": "view_coverage",
         "focus": "设计交付包的 screens 列出工序 04 的全部视图 id"},
    ],
    "06": [
        {"reviewer": "ux", "kind": "check", "check": "tokens_consumed",
         "focus": "研发代码和说明里的颜色、字号、间距都来自工序 05 的 tokens.json"},
        {"reviewer": "qa", "kind": "check", "check": "acceptance_coverage",
         "focus": "工序 04 每条验收都对应一个真实测试文件，文件里写有该条 Then"},
        {"reviewer": "qa", "kind": "llm",
         "focus": "可测试性：核心逻辑是否可被自动化测试覆盖，单测报告与 AC 是否对得上"},
    ],
    "08": [
        {"reviewer": "eng", "kind": "llm",
         "focus": "回滚与 Remote Config 降级方案在工程上能否真正执行（开关位置、回滚步骤、数据兼容）"},
    ],
    "09": [
        {"reviewer": "ba", "kind": "check", "check": "ecac_vs_ltv",
         "focus": "eCAC 熔断线不突破工序 02 的 LTV/CAC ≥ 3"},
    ],
    "10": [
        {"reviewer": "pm", "kind": "check", "check": "backlog_evidence",
         "focus": "Backlog 每一项都有留存或流失数据依据"},
        {"reviewer": "pm", "kind": "check", "check": "event_coverage",
         "focus": "运营复盘引用工序 04 埋点字典里的每一个事件编号"},
    ],
}

# Anchors a stage needs from upstream baselines before lead dispatches it.
HANDOFF_REQUIREMENTS: Dict[str, List[Dict[str, str]]] = {
    "02": [
        {"upstream": "01", "anchor": "结构化首年盘子", "pattern": r"monthly_search_volume", "computed": "som"},
    ],
    "03": [
        {"upstream": "01", "anchor": "结构化首年盘子", "pattern": r"monthly_search_volume", "computed": "som"},
        {"upstream": "02", "anchor": "价格阶梯", "pattern": r"pricing_tiers|变现阶梯", "field": "unit_economics.pricing_tiers"},
    ],
    "04": [
        {"upstream": "03", "anchor": "价值主张", "pattern": r"价值主张|uvp", "field": "direction.uvp"},
        {"upstream": "03", "anchor": "必做清单", "pattern": r"Must|必做", "field": "direction.moscow.must"},
        {"upstream": "03", "anchor": "明确不做", "pattern": r"Won't|明确不做|wont", "field": "direction.moscow.wont"},
        {"upstream": "03", "anchor": "生死假设", "pattern": r"H1", "field": "direction.hypotheses"},
    ],
    "05": [
        {"upstream": "04", "anchor": "视图 id", "pattern": r'"id"\s*:\s*"[a-z][a-z0-9_]*"|\|\s*[a-z][a-z0-9_]*\s*\|', "field": "views"},
    ],
    "06": [
        {"upstream": "04", "anchor": "验收编号 AC-xx", "pattern": r"AC-\d{2}", "field": "acceptance_criteria"},
        {"upstream": "05", "anchor": "设计稿", "pattern": r"(?i)design[ _]?tokens|tokens\.json", "field": "design.tokens_path"},
    ],
    "07": [
        {"upstream": "04", "anchor": "验收编号 AC-xx", "pattern": r"AC-\d{2}", "field": "acceptance_criteria"},
        {"upstream": "06", "anchor": "单测覆盖率 coverage_percent", "pattern": r"coverage_percent"},
    ],
    "08": [
        {"upstream": "07", "anchor": "缺陷清零记录 open_p0/open_p1", "pattern": r"open_p0"},
        {"upstream": "06", "anchor": "正式安装包", "pattern": r"app-release\.zip", "field": "engineering.packages.release"},
    ],
    "09": [
        {"upstream": "02", "anchor": "变现阶梯", "pattern": r"变现阶梯|订阅|买断"},
        {"upstream": "08", "anchor": "发布与回滚计划", "pattern": r"回滚|灰度|rollback"},
    ],
    "10": [
        {"upstream": "04", "anchor": "埋点字典", "pattern": r"埋点"},
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
# ID extraction with range expansion (AC-01~AC-04). 页面不用编号，见 view_ids_from_deliverable。
# ---------------------------------------------------------------------------

_VIEW_SLUG = re.compile(r"[a-z][a-z0-9_]{0,31}\Z")


def view_ids_from_deliverable(text: str) -> List[str]:
    """从清单的 views[].id / design.screens[].view_id，或视图表第一列，取出页面 id。"""
    ids: List[str] = []
    for obj in iter_json_objects(text or ""):
        if not isinstance(obj, dict):
            continue
        raw = obj.get("views")
        if isinstance(raw, list):
            for item in raw:
                vid = str(item.get("id") or "").strip() if isinstance(item, dict) else ""
                if _VIEW_SLUG.fullmatch(vid) and vid not in ids:
                    ids.append(vid)
        design = obj.get("design")
        if isinstance(design, dict) and isinstance(design.get("screens"), list):
            for item in design["screens"]:
                if not isinstance(item, dict):
                    continue
                vid = str(item.get("view_id") or "").strip()
                if _VIEW_SLUG.fullmatch(vid) and vid not in ids:
                    ids.append(vid)
    if ids:
        return ids
    for line in (text or "").splitlines():
        cells = [cell.strip().strip("*") for cell in line.strip().strip("|").split("|")]
        if cells and cells[0] == "id":
            continue
        if len(cells) >= 2 and _VIEW_SLUG.fullmatch(cells[0]) and cells[0] not in ids:
            ids.append(cells[0])
    return ids


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
        return _result(spec, "approve", [f"本迭代没有工序 04 基线，跳过{label}覆盖检查"])
    required = extract_ids(prefix, upstream_text)
    if not required:
        return _result(spec, "approve", [f"工序 04 基线没有 {prefix}-xx 编号"])
    present = set(extract_ids(prefix, "\n".join(texts)))
    missing = [i for i in required if i not in present]
    if missing:
        return _result(spec, "request_changes", [f"未覆盖工序 04 的{label}: {', '.join(missing)}"])
    return _result(spec, "approve", [f"已覆盖工序 04 全部{label} ({len(required)} 项)"])


def design_screen_ids(text: str) -> List[str]:
    """设计交付包清单里的 view_id。正文里提到 id 不算覆盖。"""
    ids: List[str] = []
    for obj in iter_json_objects(text or ""):
        design = obj.get("design") if isinstance(obj, dict) else None
        screens = design.get("screens") if isinstance(design, dict) else None
        if not isinstance(screens, list):
            continue
        for item in screens:
            if not isinstance(item, dict):
                continue
            vid = str(item.get("view_id") or "").strip()
            if _VIEW_SLUG.fullmatch(vid) and vid not in ids:
                ids.append(vid)
    return ids


def check_view_coverage(spec, texts, upstream, auth_data) -> Dict[str, Any]:
    upstream_text = upstream.get("04")
    if not upstream_text:
        return _result(spec, "approve", ["本迭代没有工序 04 基线，跳过视图覆盖检查"])
    required = view_ids_from_deliverable(upstream_text)
    if not required:
        return _result(spec, "approve", ["工序 04 基线没有视图 id"])
    present: List[str] = []
    for text in texts:
        for vid in design_screen_ids(text):
            if vid not in present:
                present.append(vid)
    missing = [vid for vid in required if vid not in present]
    if missing:
        return _result(spec, "request_changes", [f"设计交付包的 screens 没有工序 04 的视图: {', '.join(missing)}"])
    return _result(spec, "approve", [f"设计交付包已列出工序 04 全部视图 ({len(required)} 项)"])


def _engineering_tests(texts: List[str]) -> List[Dict[str, str]]:
    found: List[Dict[str, str]] = []
    for text in texts:
        for obj in iter_json_objects(text or ""):
            eng = obj.get("engineering") if isinstance(obj, dict) else None
            tests = eng.get("tests") if isinstance(eng, dict) else None
            if not isinstance(tests, list):
                continue
            for item in tests:
                if not isinstance(item, dict):
                    continue
                found.append({"ac": str(item.get("ac") or "").strip(), "path": str(item.get("path") or "").strip()})
    return found


def check_acceptance_coverage(spec, texts, upstream, auth_data, roots=None) -> Dict[str, Any]:
    """验收编号只认清单里的 tests，正文里写到 AC-xx 不算覆盖。目录在时还要看到测试文件。"""
    src = upstream.get("04")
    if not src:
        return _result(spec, "approve", ["本迭代没有工序 04 基线，跳过验收用例覆盖检查"])
    manifest = _manifest_of(src, "04")
    from backend.app.services.delivery_contract import acceptance_records_from

    records = acceptance_records_from(manifest or {})
    required = [item["id"] for item in records if item["id"]]
    clauses = {item["id"]: item["then"] for item in records if item["id"] and item["then"]}
    if not required:
        required = extract_ids("AC", src)
    if not required:
        return _result(spec, "approve", ["工序 04 基线没有 AC-xx 编号"])
    tests = _engineering_tests(texts)
    present = [item["ac"] for item in tests if item["ac"]]
    missing = [item for item in required if item not in present]
    findings = [f"工程清单没有把工序 04 的验收对应到测试文件: {', '.join(missing)}"] if missing else []
    root = (roots or {}).get("06")
    if root is not None:
        from backend.app.services.delivery_contract import _confined

        for item in tests:
            if item["ac"] not in required:
                continue
            path = _confined(root, item["path"])
            if path is None or not path.is_file():
                findings.append(f"验收 {item['ac']} 的测试文件不存在: {item['path'] or '(空)'}")
                continue
            clause = clauses.get(item["ac"]) or ""
            if clause and clause not in path.read_text(encoding="utf-8", errors="replace"):
                findings.append(f"验收 {item['ac']} 的测试文件没有写上 Then：{clause}")
    if findings:
        return _result(spec, "request_changes", findings)
    return _result(spec, "approve", [f"已为工序 04 全部验收编号写明测试文件 ({len(required)} 项)"])


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
_BACKLOG_ROW = re.compile(r"^\|\s*(?:\*\*)?(?:P[0-3]|BL-)", flags=re.I)


def check_backlog_evidence(spec, texts, upstream, auth_data) -> Dict[str, Any]:
    rows = [line.strip() for text in texts for line in (text or "").splitlines() if _BACKLOG_ROW.match(line.strip())]
    if not rows:
        return _result(spec, "request_changes", ["没有找到 Backlog 表格行（| P1 | 需求 | 数据依据 |）"])
    weak = [row for row in rows if not _EVIDENCE_PATTERN.search(row)]
    if weak:
        return _result(spec, "request_changes", [f"Backlog 项缺少留存/流失数据依据: {row[:80]}" for row in weak[:5]])
    return _result(spec, "approve", [f"{len(rows)} 项 Backlog 均有数据依据"])


def _joined(texts) -> str:
    return "\n".join(texts or [])


def _manifest_of(text: str, stage: str) -> Optional[Dict[str, Any]]:
    from backend.app.services.delivery_contract import manifest_from_texts, stage_code

    manifest = manifest_from_texts([text or ""])
    if manifest is None or stage_code(manifest.get("stage")) != stage:
        return None
    return manifest


def _dig(data: Dict[str, Any], path: str) -> Any:
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _number_in_text(text: str, value: float) -> bool:
    compact = re.sub(r"[,，\s]", "", text or "")
    number = float(value)
    token = str(int(number)) if number.is_integer() else f"{number:g}"
    return token in compact


def check_direction_inherits(spec, texts, upstream, auth_data) -> Dict[str, Any]:
    """方向卡必须写上工序 01 算出的首年盘子，以及工序 02 价格阶梯的每一档名称。"""
    if not upstream.get("01") and not upstream.get("02"):
        return _result(spec, "approve", ["本迭代没有工序 01 / 02 基线，跳过方向卡承接检查"])
    body = _joined(texts)
    findings: List[str] = []
    if upstream.get("01"):
        from backend.app.services.deliverable_audit import audit_som

        som = audit_som([upstream["01"]]).get("first_year_som_usd")
        if som is None:
            findings.append("工序 01 基线没有可复核的首年盘子")
        elif not _number_in_text(body, float(som)):
            findings.append(f"方向卡没有写上工序 01 的首年盘子 {float(som):,.0f}")
    manifest = _manifest_of(upstream.get("02") or "", "02")
    tiers = _dig(manifest, "unit_economics.pricing_tiers") if manifest else None
    names = [str(item.get("name")).strip() for item in tiers or [] if isinstance(item, dict) and str(item.get("name") or "").strip()]
    if names:
        missing = [name for name in names if name not in body]
        if missing:
            findings.append("方向卡没有写上工序 02 的价格档：" + "、".join(missing))
    elif upstream.get("02") and not re.search(r"变现阶梯|价格阶梯", body):
        findings.append("方向卡没有承接工序 02 的价格阶梯")
    if findings:
        return _result(spec, "request_changes", findings)
    return _result(spec, "approve", ["方向卡已写上首年盘子和价格阶梯"])


def check_direction_carried(spec, texts, upstream, auth_data) -> Dict[str, Any]:
    """需求规格必须写上方向卡里的价值主张、必做、明确不做和假设编号。"""
    src = upstream.get("03")
    if not src:
        return _result(spec, "approve", ["本迭代没有工序 03 基线，跳过方向承接检查"])
    body = _joined(texts)
    manifest = _manifest_of(src, "03")
    direction = (manifest or {}).get("direction") if manifest else None
    if not isinstance(direction, dict):
        missing = []
        if not re.search(r"价值主张|UVP|uvp", body):
            missing.append("价值主张")
        if not re.search(r"必做|Must", body):
            missing.append("必做")
        if not re.search(r"明确不做|Won't|wont", body):
            missing.append("明确不做")
        if "H1" not in body:
            missing.append("H1")
        if missing:
            return _result(spec, "request_changes", ["需求规格没有写上工序 03 的：" + "、".join(missing)])
        return _result(spec, "approve", ["需求规格已写上方向卡里的价值主张、必做、明确不做和 H1"])
    findings = []
    uvp = str(direction.get("uvp") or "").strip()
    if uvp and uvp not in body:
        findings.append(f"需求规格没有写上价值主张：{uvp}")
    moscow = direction.get("moscow") if isinstance(direction.get("moscow"), dict) else {}
    for label, key in (("必做", "must"), ("明确不做", "wont")):
        items = [str(item).strip() for item in (moscow.get(key) or []) if str(item).strip()]
        absent = [item for item in items if item not in body]
        if absent:
            findings.append(f"需求规格没有写上{label}：" + "、".join(absent))
    ids = [str(item.get("id")).strip() for item in (direction.get("hypotheses") or []) if isinstance(item, dict) and str(item.get("id") or "").strip()]
    absent_ids = [item for item in ids if item not in body]
    if absent_ids:
        findings.append("需求规格没有写上假设编号：" + "、".join(absent_ids))
    if findings:
        return _result(spec, "request_changes", findings)
    return _result(spec, "approve", ["需求规格已写上方向卡的价值主张、必做、明确不做和假设编号"])


def check_tokens_consumed(spec, texts, upstream, auth_data, roots=None) -> Dict[str, Any]:
    """颜色、字号、间距对照工序 05 的 tokens.json。说明里出现文件名不算通过。"""
    if not upstream.get("05"):
        return _result(spec, "approve", ["本迭代没有工序 05 基线，跳过色值核对"])
    roots = roots or {}
    design_root = roots.get("05")
    code_root = roots.get("06")
    if design_root is None or code_root is None:
        return _result(spec, "approve", ["没有工序目录，跳过色值核对"])
    from backend.app.services.delivery_contract import engineering_color_reasons, engineering_measure_reasons

    reasons = engineering_color_reasons(code_root, design_root)
    reasons.extend(engineering_measure_reasons(code_root, design_root))
    if reasons:
        return _result(spec, "request_changes", reasons)
    return _result(spec, "approve", ["研发交付里的颜色、字号和间距都在工序 05 的 tokens.json 中"])


def check_event_coverage(spec, texts, upstream, auth_data) -> Dict[str, Any]:
    src = upstream.get("04")
    if not src:
        return _result(spec, "approve", ["本迭代没有工序 04 基线，跳过埋点编号检查"])
    manifest = _manifest_of(src, "04")
    ids: List[str] = []
    if manifest:
        events = manifest.get("event_dictionary") or []
        ids = [str(item.get("id")).strip() for item in events if isinstance(item, dict) and str(item.get("id") or "").strip()]
    if not ids:
        ids = extract_ids("E", src)
    if not ids:
        return _result(spec, "approve", ["工序 04 基线没有埋点编号"])
    body = _joined(texts)
    missing = [item for item in ids if item not in body]
    if missing:
        return _result(spec, "request_changes", [f"运营复盘没有引用工序 04 的埋点: {', '.join(missing)}"])
    return _result(spec, "approve", [f"已引用工序 04 全部埋点编号 ({len(ids)} 项)"])


CHECKS = {
    "fakedoor_budget": check_fakedoor_budget,
    "view_coverage": check_view_coverage,
    "acceptance_coverage": check_acceptance_coverage,
    "ecac_vs_ltv": check_ecac_vs_ltv,
    "backlog_evidence": check_backlog_evidence,
    "direction_inherits": check_direction_inherits,
    "direction_carried": check_direction_carried,
    "tokens_consumed": check_tokens_consumed,
    "event_coverage": check_event_coverage,
}


def run_check(spec, texts, upstream, auth_data, roots=None) -> Dict[str, Any]:
    checker = CHECKS[spec["check"]]
    if spec["check"] in ("acceptance_coverage", "tokens_consumed"):
        return checker(spec, texts, upstream, auth_data, roots)
    return checker(spec, texts, upstream, auth_data)


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
        '"cr_target_stage": "04", "cr_flags": {}}\n\n'
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
        "cr_target_stage": str(parsed.get("cr_target_stage") or "04"),
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

def _field_present(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return len(value) > 0
    return value is not None


def anchor_satisfied(req: Dict[str, str], text: str) -> bool:
    """A structured manifest field satisfies the handoff. Older baselines keep the regex."""
    from backend.app.services.delivery_contract import manifest_from_texts, stage_code

    if req.get("computed") == "som":
        fields = merged_fields([text or ""])
        return all(fields.get(key) not in (None, "") for key in (
            "monthly_search_volume", "target_capture_rate", "blended_arpu_usd", "source",
        ))
    field = req.get("field")
    manifest = manifest_from_texts([text or ""])
    if field and manifest is not None and stage_code(manifest.get("stage")) == req["upstream"]:
        return _field_present(_dig(manifest, field))
    return bool(text and re.search(req["pattern"], text))


def check_handoff(
    module_code: str,
    upstream: Dict[str, str],
    run_stage_codes: List[str],
    roots: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, str]]:
    """Missing anchors; upstream stages absent from this run (e.g. hotfix template) are skipped.

    When a stage 05 directory is available, stage 06 also checks that tokens.json and each
    listed artboard file are still on disk.
    """
    missing = []
    roots = roots or {}
    for req in HANDOFF_REQUIREMENTS.get(str(module_code), []):
        if req["upstream"] not in run_stage_codes:
            continue
        if req.get("field") == "engineering.packages.release":
            from backend.app.services.delivery_contract import _then_by_ac

            if not _then_by_ac(roots.get("06")):
                continue
        text = upstream.get(req["upstream"]) or ""
        if not anchor_satisfied(req, text):
            missing.append(req)
            continue
        if str(module_code) == "06" and req["upstream"] == "05" and roots.get("05") is not None:
            from backend.app.services.delivery_contract import design_bundle_file_gaps

            gaps = design_bundle_file_gaps(roots.get("05"))
            if gaps:
                missing.append({**req, "anchor": "设计稿文件：" + "、".join(gaps[:6])})
        if req.get("field") == "engineering.packages.release" and roots.get("06") is not None:
            from backend.app.services.delivery_contract import release_package_file

            if release_package_file(roots.get("06")) is None:
                missing.append({**req, "anchor": "正式安装包文件"})
    return missing


def handoff_anchor_fields(text: str) -> Dict[str, Any]:
    return {k: v for k, v in merged_fields([text]).items() if k != "simulated"}


def summarize_reviews(results: List[Dict[str, Any]]) -> str:
    from backend.app.services.gate_copy import review_note
    return review_note(results)
