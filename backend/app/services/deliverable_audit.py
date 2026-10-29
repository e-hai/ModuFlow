"""Deterministic stage deliverable checks.

Gate release reads workspace files and artifact text. Caller-supplied numbers
are recorded as claims and cannot set ``passed`` by themselves.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

SKIP_DIRS = {".agents", ".git", "node_modules", "__pycache__", ".venv", "venv"}
TEXT_SUFFIXES = {".md", ".html", ".json", ".txt", ".py", ".swift", ".kt", ".m", ".ts", ".tsx", ".js"}
INFERENCE_MARKERS = (
    "CoreML",
    "MLModel",
    "onnxruntime",
    "ONNX Runtime",
    "import torch",
    "from torch",
    "transformers",
    "openai.Client",
    "generativeai",
)

_LINTER_PATH = (
    Path(__file__).resolve().parents[2]
    / "skills"
    / "pm"
    / "pm-lean-prd-guard"
    / "scripts"
    / "prd_linter.py"
)

RED_FLAG_FIELDS = {
    "touches_payment": "payment",
    "is_payment_related": "payment",
    "is_privacy_related": "privacy",
    "is_user_data_related": "user_data",
    "is_encryption_related": "encryption",
    "is_modify_lead_permissions_related": "modify_lead_permissions",
    "is_public_statement_related": "public_statement",
    "is_compliance_high_risk_related": "compliance_high_risk",
    "is_budget_exceeded": "budget_exceeded",
    "budget_exceeded": "budget_exceeded",
    "data_dictionary_schema_change": "data_dictionary_schema_change",
}


def _is_true(value: Any) -> bool:
    if value is True:
        return True
    if isinstance(value, (int, float)) and value == 1:
        return True
    if isinstance(value, str) and value.strip().lower() == "true":
        return True
    return False


def _coerce(raw: str) -> Any:
    text = raw.strip().strip("`").strip('"').strip("'")
    lowered = text.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    try:
        if "." in text:
            return float(text)
        return int(text)
    except ValueError:
        return text


def iter_json_objects(text: str) -> Iterable[Dict[str, Any]]:
    for match in re.finditer(r"```json\s*(\{.*?\})\s*```", text, flags=re.S):
        try:
            obj = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            yield obj
    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        try:
            obj = json.loads(stripped)
        except json.JSONDecodeError:
            return
        if isinstance(obj, dict):
            yield obj


def merged_fields(texts: List[str]) -> Dict[str, Any]:
    merged: Dict[str, Any] = {}
    for text in texts:
        for obj in iter_json_objects(text):
            for key, value in obj.items():
                if not isinstance(value, (dict, list)):
                    merged[key] = value
        for match in re.finditer(r"(?m)^([A-Za-z_][\w]*)\s*:\s*([^\n#]+)$", text):
            key = match.group(1)
            if key not in merged:
                merged[key] = _coerce(match.group(2).strip().rstrip(","))
    return merged


def collect_workspace_texts(workspace: Path) -> List[str]:
    texts: List[str] = []
    if workspace is None or not workspace.exists():
        return texts
    for path in workspace.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            if path.stat().st_size > 1_000_000:
                continue
            texts.append(path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
    return texts


def extract_red_flags(fields: Dict[str, Any]) -> List[str]:
    found = []
    for key, label in RED_FLAG_FIELDS.items():
        if _is_true(fields.get(key)) and label not in found:
            found.append(label)
    return found


def _number(fields: Dict[str, Any], *keys: str) -> Optional[float]:
    for key in keys:
        value = fields.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    return None


def _require(fields: Dict[str, Any], keys: List[str]) -> List[str]:
    return [key for key in keys if key not in fields or fields.get(key) in (None, "")]


def _result(passed: bool, reasons: List[str], **extra: Any) -> Dict[str, Any]:
    payload = {"passed": passed, "reasons": reasons, "evidence_found": extra.pop("evidence_found", passed or bool(reasons))}
    payload.update(extra)
    return payload


def _attach_claim(result: Dict[str, Any], claimed: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not claimed:
        return result
    result["claimed"] = claimed
    if not result.get("evidence_found"):
        result["passed"] = False
        reasons = list(result.get("reasons") or [])
        reasons.append("调用方填报的数字不能单独放行，工作区里没有对应交付物")
        result["reasons"] = reasons
    return result


def _load_prd_linter():
    spec = importlib.util.spec_from_file_location("moduflow_prd_linter", _LINTER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载 PRD linter: {_LINTER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def lint_markdown(content: str, file_name: str = "PRD.md") -> Dict[str, Any]:
    linter = _load_prd_linter()
    result = linter.lint_text(content or "", file_name)
    result["passed"] = bool(result.get("score") == 100 and result.get("passed"))
    return result


def audit_unit_economics(texts: List[str]) -> Dict[str, Any]:
    fields = merged_fields(texts)
    missing = _require(fields, [
        "organic_share", "paid_cpi_usd", "ad_arpu_usd", "iap_conversion_rate", "iap_net_arppu_usd"
    ])
    if missing:
        return _result(False, [f"单位经济交付物缺少字段: {', '.join(missing)}"], evidence_found=False, fields_found=list(fields))
    organic = float(fields["organic_share"])
    cpi = float(fields["paid_cpi_usd"])
    ad_arpu = float(fields["ad_arpu_usd"])
    conversion = float(fields["iap_conversion_rate"])
    arppu = float(fields["iap_net_arppu_usd"])
    blended_cac = round((1.0 - organic) * cpi, 3)
    ltv = round(ad_arpu + conversion * arppu, 3)
    ratio = round(ltv / blended_cac, 2) if blended_cac > 0 else 99.9
    healthy = ratio >= 3.0
    reasons = [] if healthy else [f"LTV/CAC 为 {ratio}，低于 3.0"]
    return _result(
        healthy,
        reasons,
        evidence_found=True,
        blended_cac_usd=blended_cac,
        ltv_180d_usd=ltv,
        ltv_cac_ratio=ratio,
        healthy=healthy,
    )


_SOM_MENTION = re.compile(r"(?<![A-Za-z])SOM(?![A-Za-z])|现实盘子|营收盘子|首年盘子")
_SOM_MONEY = re.compile(
    r"(?:US\$|\$|＄)\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*(万|[KkMmBb])?"
    r"|([0-9][0-9,]*(?:\.[0-9]+)?)\s*万美元"
)
_SOM_SCALE = {"万": 10000, "K": 1000, "k": 1000, "M": 1_000_000, "m": 1_000_000, "B": 1_000_000_000, "b": 1_000_000_000}


def _stated_som_amounts(text: str) -> List[float]:
    """Dollar figures a stage-01 draft states as the first-year SOM, not other prices."""
    found: List[float] = []
    for line in text.splitlines():
        if not _SOM_MENTION.search(line):
            continue
        # A SOM sentence often names the SAM beside it. That figure is not the first-year SOM.
        som_part = re.split(r"(?<![A-Za-z])SAM(?![A-Za-z])", line, maxsplit=1)[0]
        if not _SOM_MENTION.search(som_part):
            continue
        for match in _SOM_MONEY.finditer(som_part):
            raw = (match.group(1) or match.group(3) or "").replace(",", "")
            if not raw:
                continue
            value = float(raw)
            if match.group(3):
                value *= 10000
            elif match.group(2):
                value *= _SOM_SCALE[match.group(2)]
            elif value < 1000:
                continue
            found.append(value)
    return found


def _som_disagrees(stated: float, computed: float) -> bool:
    if computed <= 0:
        return abs(stated - computed) > 1
    return abs(stated - computed) / computed > 0.02


def audit_som(texts: List[str]) -> Dict[str, Any]:
    fields = merged_fields(texts)
    missing = _require(fields, ["monthly_search_volume", "target_capture_rate", "blended_arpu_usd", "source"])
    if missing:
        return _result(False, [f"SOM 交付物缺少字段: {', '.join(missing)}"], evidence_found=False)
    volume = int(float(fields["monthly_search_volume"]))
    rate = float(fields["target_capture_rate"])
    arpu = float(fields["blended_arpu_usd"])
    annual = int(volume * 12 * rate)
    som = round(annual * arpu, 2)
    mismatched: List[float] = []
    for text in texts:
        local = merged_fields([text])
        local_som = som
        if not _require(local, ["monthly_search_volume", "target_capture_rate", "blended_arpu_usd", "source"]):
            local_volume = int(float(local["monthly_search_volume"]))
            local_som = round(int(local_volume * 12 * float(local["target_capture_rate"])) * float(local["blended_arpu_usd"]), 2)
        for stated in _stated_som_amounts(text):
            if _som_disagrees(stated, local_som) and stated not in mismatched:
                mismatched.append(stated)
    reasons = []
    if mismatched:
        shown = "、".join(f"{v:,.0f}" for v in mismatched)
        reasons.append(
            f"正文里的首年盘子写的是 {shown} 美元，按月搜索量、取得比例和客单价算出的是 {som:,.2f} 美元。请把正文改成算出的数。"
        )
    return _result(
        not reasons,
        reasons,
        evidence_found=True,
        annual_target_installs=annual,
        first_year_som_usd=som,
        source=str(fields["source"]),
        verdict="GO (具备高利润截胡价值)" if som >= 100000 else "CAUTION (盘子偏小，需控研发成本)",
    )


def handoff_som_text(text: str) -> str:
    """Upstream stage 01 text for the next stage: keep the computed SOM, drop a conflicting prose figure."""
    audit = audit_som([text])
    som = audit.get("first_year_som_usd")
    if som is None:
        return text
    if not any(_som_disagrees(v, float(som)) for v in _stated_som_amounts(text)):
        return text
    kept: List[str] = []
    for line in text.splitlines():
        if any(_som_disagrees(v, float(som)) for v in _stated_som_amounts(line)):
            continue
        kept.append(line)
    kept.append(f"首年盘子以结构化字段为准：{float(som):,.2f} 美元。")
    return "\n".join(kept)


def audit_direction(texts: List[str]) -> Dict[str, Any]:
    blob = "\n".join(texts)
    reasons = []
    if not re.search(r"UVP|价值主张", blob):
        reasons.append("方向卡缺少 UVP 或价值主张")
    if not re.search(r"\bH1\b", blob):
        reasons.append("方向卡缺少 H1 假设")
    return _result(not reasons, reasons, evidence_found=bool(blob.strip()))


def linked_entry_text(storage_rel_path: Optional[str], entry_file: Optional[str] = None) -> str:
    """工序目录里的 index.html。检查器要读这个文件，不能只看归档进数据库的说明稿。"""
    if not storage_rel_path:
        return ""
    from backend.app.core.config import settings

    root = (settings.WORKSPACE_DIR / storage_rel_path).resolve()
    workspace = settings.WORKSPACE_DIR.resolve()
    if workspace != root and workspace not in root.parents:
        return ""
    entry = entry_file or "index.html"
    path = root / entry if root.is_dir() else root
    if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
        return ""
    try:
        if path.stat().st_size > 1_000_000:
            return ""
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def artifact_audit_texts(artifacts: Iterable[Any]) -> List[str]:
    texts: List[str] = []
    for artifact in artifacts:
        content = getattr(artifact, "content", None) or ""
        if content.strip():
            texts.append(content)
        extra = linked_entry_text(
            getattr(artifact, "storage_rel_path", None),
            getattr(artifact, "entry_file", None),
        )
        if extra.strip() and extra not in texts:
            texts.append(extra)
        from backend.app.services.delivery_contract import read_manifest_text

        manifest_text = read_manifest_text(getattr(artifact, "storage_rel_path", None))
        if manifest_text.strip() and manifest_text not in texts:
            texts.append(manifest_text)
    return texts


def audit_fakedoor(texts: List[str]) -> Dict[str, Any]:
    html = ""
    for text in texts:
        if "<html" in text.lower() or "<script" in text.lower() or "index.html" in text[:40]:
            if len(text) > len(html):
                html = text
    if not html:
        return _result(False, ["未找到可交互 H5 假门页面"], evidence_found=False, exists=False)
    has_script = "<script" in html.lower()
    passed = len(html) > 500 and has_script
    reasons = []
    if not has_script:
        reasons.append("H5 缺少交互脚本")
    if len(html) <= 500:
        reasons.append("H5 内容过短")
    return _result(passed, reasons, evidence_found=True, exists=True, size_bytes=len(html), has_interactive_script=has_script)


def audit_design(texts: List[str], platform: str = "ios") -> Dict[str, Any]:
    from backend.app.services.profile_guard import is_dual_platform

    fields = merged_fields(texts)
    norm = (platform or "ios").lower()
    if is_dual_platform(norm):
        ios = audit_design(texts, platform="ios")
        android = audit_design(texts, platform="android")
        reasons = list(ios["reasons"]) + list(android["reasons"])
        return _result(
            bool(ios["passed"] and android["passed"]),
            reasons,
            evidence_found=bool(ios.get("evidence_found") and android.get("evidence_found")),
            platform="cross_platform",
            ruleset="iOS HIG + Google Material Design 3 (M3)",
        )
    if norm == "android":
        top = _number(fields, "status_bar_safe_dp", "status_bar_dp", "status_bar_cutout_safe_dp")
        touch = _number(fields, "min_touch_target_dp", "min_touch_dp")
        if top is None or touch is None:
            return _result(False, ["设计交付物缺少 Android 安全区或触控热区实测值"], evidence_found=False, platform="android")
        passed = top >= 24 and touch >= 48
        reasons = []
        if top < 24:
            reasons.append(f"状态栏避让 {top}dp，低于 24dp")
        if touch < 48:
            reasons.append(f"触控热区 {touch}dp，低于 48dp")
        return _result(
            passed,
            reasons,
            evidence_found=True,
            platform="android",
            ruleset="Google Material Design 3 (M3)",
            status_bar_cutout_safe_dp=top,
            min_touch_target_dp=touch,
        )
    top = _number(fields, "top_safe_padding_pt", "dynamic_island_safe_pt")
    touch = _number(fields, "min_touch_target_pt", "min_touch_pt")
    if top is None or touch is None:
        return _result(False, ["设计交付物缺少 iOS 安全区或触控热区实测值"], evidence_found=False, platform="ios")
    passed = top >= 71 and touch >= 44
    reasons = []
    if top < 71:
        reasons.append(f"灵动岛顶部留白 {top}pt，低于 71pt")
    if touch < 44:
        reasons.append(f"触控热区 {touch}pt，低于 44pt")
    return _result(
        passed,
        reasons,
        evidence_found=True,
        platform="ios",
        ruleset="iOS Human Interface Guidelines (HIG)",
        dynamic_island_safe_pt=top,
        min_touch_pt=touch,
    )


def _inference_markers(texts: List[str]) -> List[str]:
    blob = "\n".join(texts)
    return [marker for marker in INFERENCE_MARKERS if marker in blob]


def audit_inference(texts: List[str], enforce_zero: bool = True) -> Dict[str, Any]:
    fields = merged_fields(texts)
    calls = _number(fields, "client_realtime_ai_calls")
    markers = _inference_markers(texts)
    if calls is None and not markers:
        return _result(False, ["缺少客户端推理审计记录"], evidence_found=False, enforce_zero_inference=enforce_zero)
    call_count = int(calls or 0)
    reasons = []
    if enforce_zero and (call_count != 0 or markers):
        if call_count != 0:
            reasons.append(f"客户端实时推理调用 {call_count} 次")
        if markers:
            reasons.append("交付物包含端侧推理实现: " + ", ".join(markers[:3]))
        passed = False
    else:
        passed = True
    return _result(
        passed,
        reasons,
        evidence_found=True,
        client_realtime_ai_calls=call_count,
        enforce_zero_inference=enforce_zero,
        edge_ai_permitted=not enforce_zero,
        zero_client_ai_compliant=call_count == 0 and not markers,
        inference_markers=markers,
    )


def audit_coverage(texts: List[str]) -> Dict[str, Any]:
    fields = merged_fields(texts)
    coverage = _number(fields, "coverage_percent", "line_coverage_percent")
    ratio = _number(fields, "coverage", "line_rate")
    if coverage is None and ratio is not None:
        coverage = ratio * 100 if ratio <= 1 else ratio
    if coverage is None:
        return _result(False, ["缺少核心逻辑单测覆盖率"], evidence_found=False)
    passed = coverage >= 80
    reasons = [] if passed else [f"单测覆盖率 {coverage}%，低于 80%"]
    return _result(passed, reasons, evidence_found=True, coverage_percent=coverage)


def audit_quality(texts: List[str], require_remote_config: bool = False) -> Dict[str, Any]:
    fields = merged_fields(texts)
    p0 = _number(fields, "open_p0", "open_critical_issues")
    p1 = _number(fields, "open_p1", "open_major_issues")
    if p0 is None or p1 is None:
        return _result(False, ["质量报告缺少 open_p0 / open_p1"], evidence_found=False)
    reasons = []
    if p0 != 0:
        reasons.append(f"未关闭 P0: {int(p0)}")
    if p1 != 0:
        reasons.append(f"未关闭 P1: {int(p1)}")
    remote = fields.get("has_remote_config_fallback")
    if require_remote_config and not _is_true(remote):
        reasons.append("缺少 Remote Config 降级开关记录")
    return _result(
        not reasons,
        reasons,
        evidence_found=True,
        open_p0=int(p0),
        open_p1=int(p1),
        has_remote_config_fallback=_is_true(remote),
    )


def audit_acquisition(texts: List[str]) -> Dict[str, Any]:
    fields = merged_fields(texts)
    ecac = _number(fields, "ecac_usd")
    limit = _number(fields, "ecac_limit_usd")
    if ecac is None or limit is None:
        return _result(False, ["获客交付物缺少 ecac_usd 或 ecac_limit_usd"], evidence_found=False)
    passed = ecac <= limit
    reasons = [] if passed else [f"eCAC {ecac} 超过熔断线 {limit}"]
    return _result(passed, reasons, evidence_found=True, ecac_usd=ecac, ecac_limit_usd=limit)


def audit_retention(texts: List[str]) -> Dict[str, Any]:
    fields = merged_fields(texts)
    d1 = _number(fields, "d1_retention", "d1")
    d7 = _number(fields, "d7_retention", "d7")
    d30 = _number(fields, "d30_retention", "d30")
    blob = "\n".join(texts)
    if d1 is None or d7 is None or d30 is None:
        return _result(False, ["留存报告缺少 D1/D7/D30"], evidence_found=False)
    reasons = []
    if not re.search(r"V1\.1|Backlog|backlog", blob):
        reasons.append("缺少 V1.1 Backlog")
    return _result(
        not reasons,
        reasons,
        evidence_found=True,
        d1_retention=d1,
        d7_retention=d7,
        d30_retention=d30,
        d1_d7_drop_ratio=round((d1 - d7) / max(d1, 1.0), 2),
        d30_healthy=d30 >= 8.0,
    )


def audit_prd(texts: List[str]) -> Dict[str, Any]:
    if not any(text.strip() for text in texts):
        return _result(False, ["没有 PRD 交付物"], evidence_found=False, score=0)
    best = None
    for index, text in enumerate(texts):
        if not text.strip():
            continue
        current = lint_markdown(text, f"artifact-{index}.md")
        if best is None or current.get("score", 0) > best.get("score", 0):
            best = current
    assert best is not None
    reasons = list(best.get("warnings") or [])
    if not best.get("passed"):
        reasons.insert(0, f"PRD 得分 {best.get('score')}，放行线为 100")
    return _result(bool(best.get("passed")), reasons, evidence_found=True, score=best.get("score"), linter=best)


# Stage 01 may cite competitor prices as market intel; stage 02 (ba) is the pricing source.
PRICING_EXEMPT_STAGES = {"01", "02"}
_PRICE_PATTERN = re.compile(
    r"(?:US\$|\$|¥|￥|€|£)\s?(\d+(?:\.\d{1,2})?)"
    r"|(\d+(?:\.\d{1,2})?)\s?(?:美元|元|usd|USD)"
)
_PRICING_CONTEXT = re.compile(
    r"价格|定价|售价|标价|订阅|通行证|买断|周卡|月卡|年卡|内购|sku|price|pricing|"
    r"/\s?(?:月|周|年)|/\s?(?:mo|yr|week|month|year)\b|per (?:week|month|year)",
    flags=re.I,
)
_NON_PRICING_CONTEXT = re.compile(
    r"预算|成本|花费|支出|收入|营收|cac|cpi|cpm|cpc|arpu|arppu|ltv|som|tam|sam|budget|spend|revenue|cost|"
    r"竞品|competitor",
    flags=re.I,
)


def extract_price_points(text: str) -> List[float]:
    values: List[float] = []
    for match in _PRICE_PATTERN.finditer(text or ""):
        raw = match.group(1) or match.group(2)
        try:
            values.append(round(float(raw), 2))
        except (TypeError, ValueError):
            continue
    return values


def find_unbaselined_prices(texts: List[str], baseline_prices: Iterable[float]) -> List[str]:
    """Lines quoting a price (pricing wording + amount) whose amount is not in the stage 02 baseline."""
    allowed = {round(float(p), 2) for p in baseline_prices}
    offending: List[str] = []
    for text in texts:
        for line in (text or "").splitlines():
            if not _PRICING_CONTEXT.search(line) or _NON_PRICING_CONTEXT.search(line):
                continue
            unknown = [p for p in extract_price_points(line) if p not in allowed]
            if unknown:
                offending.append(line.strip()[:120])
    return offending


def audit_pricing_authority(module_code: str, texts: List[str], baseline_prices: Iterable[float]) -> Dict[str, Any]:
    if str(module_code) in PRICING_EXEMPT_STAGES:
        return _result(True, [], evidence_found=True)
    offending = find_unbaselined_prices(texts, baseline_prices)
    reasons = [
        f"出现工序 02 定价基线之外的价格（价格唯一来源是 ba，改价须走工序 02 CR）：{line}"
        for line in offending[:5]
    ]
    return _result(not offending, reasons, evidence_found=True, offending_lines=offending)


def _audit_stage_text(
    code: str,
    texts: List[str],
    platform: str = "ios",
    client_zero_inference: bool = True,
) -> Dict[str, Any]:
    if code == "01":
        return audit_som(texts)
    if code == "02":
        return audit_unit_economics(texts)
    if code == "03":
        return audit_direction(texts)
    if code == "04":
        return audit_fakedoor(texts)
    if code == "05":
        return audit_prd(texts)
    if code == "06":
        return audit_design(texts, platform=platform)
    if code == "07":
        inference = audit_inference(texts, enforce_zero=client_zero_inference)
        coverage = audit_coverage(texts)
        reasons = list(inference.get("reasons") or []) + list(coverage.get("reasons") or [])
        return _result(
            bool(inference.get("passed") and coverage.get("passed")),
            reasons,
            evidence_found=bool(inference.get("evidence_found") and coverage.get("evidence_found")),
            inference=inference,
            coverage=coverage,
        )
    if code == "08":
        return audit_quality(texts, require_remote_config=False)
    if code == "09":
        return audit_quality(texts, require_remote_config=True)
    if code == "10":
        return audit_acquisition(texts)
    if code == "11":
        return audit_retention(texts)
    return _result(False, [f"工序 {code} 没有确定性检查器"], evidence_found=False)


def _prose_texts(texts: List[str]) -> List[str]:
    from backend.app.services.delivery_contract import manifest_from_texts

    prose = [text for text in texts if manifest_from_texts([text]) is None]
    return prose or texts


def audit_stage(
    module_code: str,
    texts: List[str],
    platform: str = "ios",
    client_zero_inference: bool = True,
    price_baseline: Optional[Iterable[float]] = None,
    manifest_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """price_baseline=None skips the pricing-authority check (no run context available)."""
    from backend.app.services.delivery_contract import (
        CONTRACT_STAGES,
        manifest_from_texts,
        risk_fields_from_manifest,
        stage_code,
        validate_manifest,
    )

    code = str(module_code)
    manifest = manifest_from_texts(texts)
    if manifest is None and manifest_root is not None:
        from backend.app.services.delivery_contract import MANIFEST_FILENAME

        manifest_path = manifest_root / MANIFEST_FILENAME
        if manifest_path.is_file():
            manifest = manifest_from_texts([manifest_path.read_text(encoding="utf-8", errors="replace")])
    use_manifest = (
        manifest is not None
        and stage_code(manifest.get("stage")) == code
        and code in CONTRACT_STAGES
    )
    if use_manifest:
        assert manifest is not None
        reasons = validate_manifest(
            manifest,
            root=manifest_root,
            texts=texts,
            platform=platform,
            client_zero_inference=client_zero_inference,
        )
        red_flags = extract_red_flags(risk_fields_from_manifest(manifest))
        extra: Dict[str, Any] = {"contract": "delivery.manifest.json"}
        if code == "01":
            mr = manifest.get("market_research") or manifest.get("som") or {}
            extra.update({
                "annual_target_installs": mr.get("annual_target_installs"),
                "first_year_som_usd": mr.get("first_year_som_usd"),
                "source": str(mr.get("source") or ""),
                "verdict": mr.get("verdict"),
            })
        elif code == "02":
            ue = manifest.get("unit_economics") or {}
            extra.update({
                "blended_cac_usd": ue.get("blended_cac_usd"),
                "ltv_180d_usd": ue.get("ltv_180d_usd"),
                "ltv_cac_ratio": ue.get("ltv_cac_ratio"),
                "healthy": (ue.get("ltv_cac_ratio") or 0) >= 3.0,
            })
        elif code == "03":
            dir_data = manifest.get("direction") or {}
            raw_hyps = dir_data.get("hypotheses") or []
            hyps = [
                h.get("hypothesis") if isinstance(h, dict) else str(h)
                for h in raw_hyps
            ]
            extra.update({
                "uvp": dir_data.get("uvp"),
                "hypotheses": hyps,
            })
        elif code == "04":
            fd = manifest.get("fakedoor") or {}
            extra.update({
                "exists": True,
                "test_budget_usd": fd.get("test_budget_usd", 200.0),
            })
        elif code == "05":
            prd = audit_prd(_prose_texts(texts))
            extra["score"] = prd.get("score")
            extra["linter"] = prd.get("linter")
            if not prd.get("passed"):
                reasons.extend(prd.get("reasons") or [])
        elif code == "06":
            des = manifest.get("design") or {}
            safe_area = des.get("safe_area") or {}
            touch = des.get("touch_targets") or {}
            extra.update({
                "platform": des.get("platform", platform),
                "dynamic_island_safe_pt": safe_area.get("top_safe_padding_pt"),
                "min_touch_pt": touch.get("min_touch_target_pt"),
                "status_bar_cutout_safe_dp": safe_area.get("status_bar_safe_dp"),
                "min_touch_target_dp": touch.get("min_touch_target_dp"),
            })
        elif code == "07":
            eng = manifest.get("engineering") or {}
            cov = eng.get("coverage_percent", 0.0)
            zero = eng.get("zero_client_inference", True)
            extra.update({
                "coverage_percent": cov,
                "coverage": {"coverage_percent": cov},
                "inference": {"zero_client_ai_compliant": zero},
            })
        elif code == "08":
            qa = manifest.get("quality") or {}
            extra.update({
                "open_p0": qa.get("open_p0", 0),
                "open_p1": qa.get("open_p1", 0),
            })
        elif code == "09":
            rel = manifest.get("release") or {}
            extra.update({
                "open_p0": 0,
                "open_p1": 0,
                "has_remote_config_fallback": rel.get("has_remote_killswitch", True),
            })
        elif code == "10":
            acq = manifest.get("acquisition") or {}
            extra.update({
                "ecac_usd": acq.get("ecac_usd"),
                "ecac_limit_usd": acq.get("ecac_limit_usd"),
            })
        elif code == "11":
            ret = manifest.get("retention") or {}
            extra.update({
                "d1_retention": ret.get("d1_retention"),
                "d7_retention": ret.get("d7_retention"),
                "d30_retention": ret.get("d30_retention"),
                "d30_healthy": (ret.get("d30_retention") or 0) >= 8.0,
            })
        result = _result(not reasons, reasons, evidence_found=True, **extra)
    else:
        fields = merged_fields(texts)
        red_flags = extract_red_flags(fields)
        result = _audit_stage_text(
            code, texts, platform=platform, client_zero_inference=client_zero_inference,
        )
    if price_baseline is not None:
        pricing = audit_pricing_authority(code, texts, price_baseline)
        result["pricing"] = pricing
        if not pricing["passed"]:
            result["passed"] = False
            result["reasons"] = list(result.get("reasons") or []) + list(pricing["reasons"])
    result["red_flags"] = red_flags
    result["module_code"] = code
    from backend.app.services.gate_copy import build_stage_brief
    brief = build_stage_brief(code, texts, result)
    result["brief"] = brief
    if result.get("passed") and brief.get("missing"):
        result["passed"] = False
        result["reasons"] = list(result.get("reasons") or []) + [
            "交给项目总控的汇报缺少：" + "、".join(brief["missing"])
        ]
    return result


def audit_unit_economics_workspace(workspace: Path, claimed: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return _attach_claim(audit_unit_economics(collect_workspace_texts(workspace)), claimed)


def _som_preview(claimed: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not claimed:
        return {}
    try:
        volume = int(float(claimed["monthly_search_volume"]))
        rate = float(claimed["target_capture_rate"])
        arpu = float(claimed["blended_arpu_usd"])
    except (KeyError, TypeError, ValueError):
        return {}
    annual = int(volume * 12 * rate)
    som = round(annual * arpu, 2)
    return {
        "annual_target_installs": annual,
        "first_year_som_usd": som,
        "verdict": "GO (具备高利润截胡价值)" if som >= 100000 else "CAUTION (盘子偏小，需控研发成本)",
    }


def audit_som_workspace(workspace: Path, claimed: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    result = _attach_claim(audit_som(collect_workspace_texts(workspace)), claimed)
    if claimed and not result.get("evidence_found"):
        result.update(_som_preview(claimed))
        result["passed"] = False
    return result


def audit_design_workspace(workspace: Path, platform: str = "ios", claimed: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return _attach_claim(audit_design(collect_workspace_texts(workspace), platform=platform), claimed)


def audit_inference_workspace(workspace: Path, claimed: Optional[Dict[str, Any]] = None, enforce_zero: Optional[bool] = None) -> Dict[str, Any]:
    if enforce_zero is None:
        enforce_zero = os.getenv("MODUFLOW_ZERO_INFERENCE", "true").lower() != "false"
    return _attach_claim(audit_inference(collect_workspace_texts(workspace), enforce_zero=enforce_zero), claimed)


def audit_qa_workspace(workspace: Path, claimed: Optional[Dict[str, Any]] = None, require_remote_config: bool = False) -> Dict[str, Any]:
    return _attach_claim(audit_quality(collect_workspace_texts(workspace), require_remote_config=require_remote_config), claimed)


def audit_retention_workspace(workspace: Path, claimed: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return _attach_claim(audit_retention(collect_workspace_texts(workspace)), claimed)


def audit_fakedoor_workspace(workspace: Path, claimed: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    texts = collect_workspace_texts(workspace)
    return _attach_claim(audit_fakedoor(texts), claimed)
