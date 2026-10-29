"""Structured handoff across all 11 stages (01 to 11).

The checker reads delivery.manifest.json field by field. A stage directory
without that file keeps the existing prose checks.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

MANIFEST_FILENAME = "delivery.manifest.json"
CONTRACT_VERSION = "1"
CONTRACT_STAGES = {f"{i:02d}" for i in range(1, 12)}

RISK_FLAG_KEYS = (
    "payment",
    "privacy",
    "user_data",
    "encryption",
    "lead_permissions",
    "public_statement",
    "data_dictionary",
)

_RISK_TO_AUDIT = {
    "payment": "is_payment_related",
    "privacy": "is_privacy_related",
    "user_data": "is_user_data_related",
    "encryption": "is_encryption_related",
    "lead_permissions": "is_modify_lead_permissions_related",
    "public_statement": "is_public_statement_related",
    "data_dictionary": "data_dictionary_schema_change",
}

_VIEW_ID = re.compile(r"V-\d{2}\Z")
_AC_ID = re.compile(r"AC-\d{2}\Z")


def stage_code(value: Any) -> str:
    text = str(value or "").strip()
    if text.isdigit():
        return text.zfill(2)
    return text


def manifest_instruction(module_code: str, filename: str) -> str:
    """Tell the primary agent to revise the manifest together with the prose."""
    code = stage_code(module_code)
    if code not in CONTRACT_STAGES:
        return ""
    lines = [
        f"同时维护本目录的 `{MANIFEST_FILENAME}`，contract_version 为 \"1\"，stage 为 \"{code}\"。",
        f"artifacts 用 role 和 path 指向 `{filename}`"
        + (" 和 `index.html`" if code == "04" else "")
        + "，路径必须留在本工序目录内。",
        "修订时清单和正文一起改，只改长文不算完成。",
        "risk_flags 的 payment、privacy、user_data、encryption、lead_permissions、public_statement、data_dictionary 都写布尔值。红级只认这些字段。",
    ]
    if code == "01":
        lines.append(
            "market_research 必须包含 monthly_search_volume、target_capture_rate、blended_arpu_usd、"
            "annual_target_installs、first_year_som_usd、source 和 verdict。数字必须可复算且附带真实来源。"
        )
    elif code == "02":
        lines.append(
            "unit_economics 必须包含 organic_share、paid_cpi_usd、ad_arpu_usd、iap_conversion_rate、"
            "iap_net_arppu_usd、blended_cac_usd、ltv_180d_usd、ltv_cac_ratio（≥3.0）以及 pricing_tiers。"
            "全平台价格阶梯以此清单为唯一真理源。"
        )
    elif code == "03":
        lines.append(
            "direction 必须包含 uvp、moscow（含 must 数组）以及 hypotheses 假设清单（至少含 H1）。"
        )
    elif code == "04":
        lines.append(
            "fakedoor.entry 指向 index.html，interactive 为 true。"
            "没有真实外测时 measured_results 必须是 \"pending\"，不要编造 CTR。"
        )
    elif code == "05":
        lines.append("views、acceptance_criteria 用编号数组（V-01、AC-01）。event_dictionary 每项含 id 和 name。")
        lines.append(
            "compliance 写 uses_idfa、att_copy、att_denied_fallback、uses_ad_id、"
            "ad_id_permission_declared、min_audience_age、ad_id_opt_out_fallback。"
            "不使用 IDFA 或 AD_ID 时把对应 uses_* 标为 false，不要靠正文里出现 ATT 这三个字母。"
        )
    elif code == "06":
        lines.append(
            "design 是设计交付包清单，必须包含 platform、entry（index.html 设计工作台）、tokens_path（tokens.json）、"
            "screens（每个工序 05 视图一项：view_id、path 为 screens/V-xx.html、platforms）和 icons（assets/icons/*.svg 路径列表）。"
            "每张画板必须有 iOS/Android 设备外框（data-device、data-safe-top、data-safe-bottom）、四态面板（data-state）、"
            "可点击元素的 data-hit 热区标注，颜色只能来自 tokens.json，零外部依赖。"
            "iOS 顶部 ≥ 71pt、底部 ≥ 34pt、触控 ≥ 44pt；Android 状态栏 ≥ 24dp、触控 ≥ 48dp。"
        )
    elif code == "07":
        lines.append(
            "engineering 必须包含 coverage_percent（核心单测 ≥ 80）以及 zero_client_inference（按 profile 声明端侧零推理）。"
        )
    elif code == "08":
        lines.append(
            "quality 必须包含 open_p0（必须为 0）、open_p1（必须为 0）、test_cases_total 与 test_cases_passed。"
        )
    elif code == "09":
        lines.append(
            "release 必须包含 store_targets、compliance_checked（true）、has_remote_killswitch（true）与 rollback_plan（回滚预案）。"
        )
    elif code == "10":
        lines.append(
            "acquisition 必须包含 ecac_usd、ecac_limit_usd（熔断线）、channels 与 daily_budget_usd。"
        )
    elif code == "11":
        lines.append(
            "retention 必须包含 d1_retention、d7_retention、d30_retention 与 backlog_items（增量需求建议）。"
        )
    return " ".join(lines)


def build_stage_manifest(
    module_code: str,
    report_path: str,
    platform: str = "cross_platform",
    views: Optional[List[str]] = None,
) -> str:
    """Simulator manifest across all 11 stages. Stage 04 leaves measured results pending."""
    code = stage_code(module_code)
    flags = {key: False for key in RISK_FLAG_KEYS}
    if code == "01":
        volume = 120000
        rate = 0.05
        arpu = 15.0
        annual = int(volume * 12 * rate)
        som = round(annual * arpu, 2)
        data: Dict[str, Any] = {
            "contract_version": CONTRACT_VERSION,
            "stage": "01",
            "artifacts": [{"role": "report", "path": report_path}],
            "risk_flags": flags,
            "market_research": {
                "monthly_search_volume": volume,
                "target_capture_rate": rate,
                "blended_arpu_usd": arpu,
                "annual_target_installs": annual,
                "first_year_som_usd": som,
                "source": "Google Keyword Planner & Sensor Tower Q3 2026",
                "verdict": "GO (具备高利润截胡价值)" if som >= 100000 else "CAUTION (盘子偏小，需控研发成本)",
            },
        }
    elif code == "02":
        organic = 0.35
        cpi = 1.2
        ad_arpu = 0.8
        conversion = 0.05
        arppu = 38.0
        blended_cac = round((1.0 - organic) * cpi, 3)
        ltv = round(ad_arpu + conversion * arppu, 3)
        ratio = round(ltv / blended_cac, 2) if blended_cac > 0 else 99.9
        data = {
            "contract_version": CONTRACT_VERSION,
            "stage": "02",
            "artifacts": [{"role": "report", "path": report_path}],
            "risk_flags": flags,
            "unit_economics": {
                "organic_share": organic,
                "paid_cpi_usd": cpi,
                "ad_arpu_usd": ad_arpu,
                "iap_conversion_rate": conversion,
                "iap_net_arppu_usd": arppu,
                "blended_cac_usd": blended_cac,
                "ltv_180d_usd": ltv,
                "ltv_cac_ratio": ratio,
                "payback_months": 3.5,
                "pricing_tiers": [
                    {"tier_id": "free", "name": "免费体验版", "price_usd": 0.0, "billing_period": "forever"},
                    {"tier_id": "day_pass", "name": "24小时应急通行证", "price_usd": 2.99, "billing_period": "24h"},
                    {"tier_id": "subscription_monthly", "name": "月度高质会员", "price_usd": 9.99, "billing_period": "monthly"},
                    {"tier_id": "lifetime", "name": "终身买断卡", "price_usd": 49.99, "billing_period": "lifetime"},
                ],
            },
        }
    elif code == "03":
        data = {
            "contract_version": CONTRACT_VERSION,
            "stage": "03",
            "artifacts": [{"role": "direction_card", "path": report_path}],
            "risk_flags": flags,
            "direction": {
                "uvp": "为目标画像提供「即开即用、无广告打断」的核心体验",
                "target_audience": "海外中小型电商卖家与社媒创作者",
                "moscow": {
                    "must": ["核心主流程", "结果保存"],
                    "should": ["收藏与历史"],
                    "could": ["分享卡片"],
                    "wont": ["社交评论", "多级目录"],
                },
                "hypotheses": [
                    {"id": "H1", "hypothesis": "目标用户愿意为无广告体验与高质导出付费", "validation_stage": "04"},
                    {"id": "H2", "hypothesis": "极简前后对比着陆页转化率 ≥ 5%", "validation_stage": "04"},
                ],
            },
        }
    elif code == "04":
        data = {
            "contract_version": CONTRACT_VERSION,
            "stage": "04",
            "artifacts": [
                {"role": "report", "path": report_path},
                {"role": "fakedoor", "path": "index.html"},
            ],
            "risk_flags": flags,
            "fakedoor": {
                "entry": "index.html",
                "interactive": True,
                "test_budget_usd": 200.0,
                "measured_results": "pending",
            },
        }
    elif code == "05":
        data = {
            "contract_version": CONTRACT_VERSION,
            "stage": "05",
            "artifacts": [{"role": "prd", "path": report_path}],
            "risk_flags": flags,
            "views": ["V-01", "V-02", "V-03", "V-04"],
            "acceptance_criteria": ["AC-01", "AC-02"],
            "event_dictionary": [
                {"id": "E-01", "name": "generate_start"},
                {"id": "E-02", "name": "generate_success"},
                {"id": "E-03", "name": "save_result"},
            ],
            "compliance": {"uses_idfa": False, "uses_ad_id": False},
        }
    elif code == "06":
        from backend.app.services.design_bundle_sim import design_manifest_block

        artifacts_06 = [
            {"role": "design_spec", "path": report_path},
            {"role": "design_workbench", "path": "index.html"},
            {"role": "design_tokens", "path": "tokens.json"},
        ]
        view_list = views or ["V-01", "V-02", "V-03", "V-04"]
        artifacts_06 += [{"role": "design_screen", "path": f"screens/{view}.html"} for view in view_list]
        data = {
            "contract_version": CONTRACT_VERSION,
            "stage": "06",
            "artifacts": artifacts_06,
            "risk_flags": flags,
            "design": design_manifest_block(platform, view_list),
        }
    elif code == "07":
        data = {
            "contract_version": CONTRACT_VERSION,
            "stage": "07",
            "artifacts": [{"role": "architecture_spec", "path": report_path}],
            "risk_flags": flags,
            "engineering": {
                "coverage_percent": 85.0,
                "zero_client_inference": True,
                "modules": ["auth", "core_pipeline", "storage_sync"],
            },
        }
    elif code == "08":
        data = {
            "contract_version": CONTRACT_VERSION,
            "stage": "08",
            "artifacts": [{"role": "test_report", "path": report_path}],
            "risk_flags": flags,
            "quality": {
                "open_p0": 0,
                "open_p1": 0,
                "test_cases_total": 42,
                "test_cases_passed": 42,
                "e2e_pass_rate": 1.0,
            },
        }
    elif code == "09":
        data = {
            "contract_version": CONTRACT_VERSION,
            "stage": "09",
            "artifacts": [{"role": "release_notes", "path": report_path}],
            "risk_flags": flags,
            "release": {
                "store_targets": ["app_store", "google_play"],
                "compliance_checked": True,
                "has_remote_killswitch": True,
                "rollback_plan": "如遇严重缺陷，通过 Remote Config 关闭新特性，立即回滚至上一稳定版本。",
            },
        }
    elif code == "10":
        data = {
            "contract_version": CONTRACT_VERSION,
            "stage": "10",
            "artifacts": [{"role": "marketing_plan", "path": report_path}],
            "risk_flags": flags,
            "acquisition": {
                "ecac_usd": 1.85,
                "ecac_limit_usd": 2.5,
                "channels": ["meta_ads", "google_search"],
                "daily_budget_usd": 150.0,
            },
        }
    elif code == "11":
        data = {
            "contract_version": CONTRACT_VERSION,
            "stage": "11",
            "artifacts": [{"role": "retention_review", "path": report_path}],
            "risk_flags": flags,
            "retention": {
                "d1_retention": 42.0,
                "d7_retention": 22.5,
                "d30_retention": 11.0,
                "backlog_items": [
                    "P1: 新增批量导出功能（依据：流失用户中 35% 反馈单张导出繁琐）",
                    "P2: 优化黑暗模式对比度（依据：留存用户夜间使用时长占比 40%）",
                ],
            },
        }
    else:
        return ""
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def bind_manifest_report_path(manifest_text: str, report_path: str) -> str:
    data = json.loads(manifest_text)
    for item in data.get("artifacts") or []:
        if isinstance(item, dict) and item.get("role") in {
            "report", "prd", "direction_card", "design_spec",
            "architecture_spec", "test_report", "release_notes",
            "marketing_plan", "retention_review",
        }:
            item["path"] = report_path
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def _workspace_root():
    from backend.app.core.config import settings

    return settings.WORKSPACE_DIR.resolve()


def _confined(root: Path, relative: str) -> Optional[Path]:
    rel = (relative or "").strip()
    if not rel or rel.startswith(("/", "\\")):
        return None
    parts = Path(rel).parts
    if any(part == ".." for part in parts):
        return None
    base = root.resolve()
    target = (base / rel).resolve()
    if target != base and base not in target.parents:
        return None
    return target


def stage_directory(artifacts: Iterable[Any]) -> Optional[Path]:
    """Stage workspace that holds the latest artifact, if it stays under the workspace root."""
    workspace = _workspace_root()
    found: Optional[Path] = None
    for artifact in artifacts or []:
        rel = getattr(artifact, "storage_rel_path", None)
        if not rel:
            continue
        root = (workspace / rel).resolve()
        if workspace != root and workspace not in root.parents:
            continue
        directory = root if root.is_dir() else root.parent
        if directory.is_dir():
            found = directory
    return found


def read_manifest_text(storage_rel_path: Optional[str]) -> str:
    if not storage_rel_path:
        return ""
    workspace = _workspace_root()
    root = (workspace / storage_rel_path).resolve()
    if workspace != root and workspace not in root.parents:
        return ""
    directory = root if root.is_dir() else root.parent
    path = directory / MANIFEST_FILENAME
    if not path.is_file():
        return ""
    try:
        if path.stat().st_size > 200_000:
            return ""
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def iter_json_documents(text: str) -> Iterable[Dict[str, Any]]:
    raw = text or ""
    stripped = raw.strip()
    if stripped.startswith("{"):
        try:
            data = json.loads(stripped)
        except json.JSONDecodeError:
            data = None
        if isinstance(data, dict):
            yield data
            return
    decoder = json.JSONDecoder()
    for fence in re.finditer(r"```json\s*", raw):
        try:
            data, _ = decoder.raw_decode(raw[fence.end():])
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            yield data


def manifest_from_texts(texts: Iterable[str]) -> Optional[Dict[str, Any]]:
    found: Optional[Dict[str, Any]] = None
    for text in texts:
        for doc in iter_json_documents(text or ""):
            if "contract_version" in doc and "stage" in doc:
                found = doc
    return found


def risk_fields_from_manifest(manifest: Dict[str, Any]) -> Dict[str, bool]:
    flags = manifest.get("risk_flags") if isinstance(manifest.get("risk_flags"), dict) else {}
    return {audit_key: bool(flags.get(flag_key)) for flag_key, audit_key in _RISK_TO_AUDIT.items()}


def _is_bool(value: Any) -> bool:
    return isinstance(value, bool)


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _html_text(texts: Iterable[str]) -> str:
    best = ""
    for text in texts:
        if "<html" in (text or "").lower() or "<script" in (text or "").lower():
            if len(text) > len(best):
                best = text
    return best


def _entry_html(entry: str, root: Optional[Path], texts: List[str]) -> str:
    if root is not None and entry:
        path = _confined(root, entry)
        if path is not None and path.is_file():
            try:
                return path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                return ""
        return ""
    return _html_text(texts)


# --- Stage-specific validators ---

def _validate_stage01(data: Dict[str, Any]) -> List[str]:
    reasons: List[str] = []
    mr = data.get("market_research") or data.get("som")
    if not isinstance(mr, dict):
        return ["market_research：缺少赛道摸底与 SOM 数据对象"]
    vol = mr.get("monthly_search_volume")
    rate = mr.get("target_capture_rate")
    arpu = mr.get("blended_arpu_usd")
    source = mr.get("source")
    if not _is_number(vol) or vol < 0:
        reasons.append("market_research.monthly_search_volume：必须是非负数字")
    if not _is_number(rate) or rate < 0 or rate > 1:
        reasons.append("market_research.target_capture_rate：必须在 0 到 1 之间")
    if not _is_number(arpu) or arpu < 0:
        reasons.append("market_research.blended_arpu_usd：必须是非负数字")
    if not _nonempty(source):
        reasons.append("market_research.source：必须注明真实数据来源或假设说明")
    return reasons


def _validate_stage02(data: Dict[str, Any]) -> List[str]:
    reasons: List[str] = []
    ue = data.get("unit_economics")
    if not isinstance(ue, dict):
        return ["unit_economics：缺少单位经济模型对象"]
    for key in ("organic_share", "paid_cpi_usd", "ad_arpu_usd", "iap_conversion_rate", "iap_net_arppu_usd"):
        if not _is_number(ue.get(key)):
            reasons.append(f"unit_economics.{key}：缺少或非数字")
    ratio = ue.get("ltv_cac_ratio")
    if not _is_number(ratio):
        reasons.append("unit_economics.ltv_cac_ratio：缺少或非数字")
    elif ratio < 3.0:
        reasons.append(f"unit_economics.ltv_cac_ratio：预测值为 {ratio}，低于 3.0 健康线")
    tiers = ue.get("pricing_tiers")
    if not isinstance(tiers, list) or not tiers:
        reasons.append("unit_economics.pricing_tiers：必须包含价格阶梯列表（全平台唯一真理源）")
    else:
        for index, item in enumerate(tiers):
            if not isinstance(item, dict) or not _nonempty(str(item.get("name") or "")) or not _is_number(item.get("price_usd")):
                reasons.append(f"unit_economics.pricing_tiers[{index}]：缺少 name 或非数字 price_usd")
                break
    return reasons


def _validate_stage03(data: Dict[str, Any]) -> List[str]:
    reasons: List[str] = []
    direction = data.get("direction")
    if not isinstance(direction, dict):
        return ["direction：缺少精益方向定义对象"]
    if not _nonempty(direction.get("uvp")):
        reasons.append("direction.uvp：缺少核心价值主张 (UVP)")
    moscow = direction.get("moscow")
    if not isinstance(moscow, dict) or not isinstance(moscow.get("must"), list) or not moscow.get("must"):
        reasons.append("direction.moscow.must：必须包含 MVP 交付范围清单")
    hypotheses = direction.get("hypotheses")
    has_h1 = False
    if isinstance(hypotheses, list) and hypotheses:
        for hyp in hypotheses:
            if isinstance(hyp, dict) and "H1" in str(hyp.get("id") or ""):
                has_h1 = True
            elif isinstance(hyp, str) and "H1" in hyp:
                has_h1 = True
    if not has_h1:
        reasons.append("direction.hypotheses：必须包含生死假设 H1")
    return reasons


def _validate_fakedoor(fakedoor: Any, root: Optional[Path], texts: List[str]) -> List[str]:
    if not isinstance(fakedoor, dict):
        return ["fakedoor：缺少 entry、interactive、measured_results"]
    reasons: List[str] = []
    entry = fakedoor.get("entry")
    if not isinstance(entry, str) or not entry.strip():
        reasons.append("fakedoor.entry：缺少假门入口文件")
    else:
        entry = entry.strip()
        if entry.startswith(("/", "\\")) or ".." in Path(entry).parts:
            reasons.append("fakedoor.entry：必须留在本工序目录内")
        else:
            html = _entry_html(entry, root, texts)
            if not html.strip():
                reasons.append(f"fakedoor.entry：未找到 {entry}")
            elif "<script" not in html.lower() or len(html) <= 500:
                reasons.append("fakedoor.entry：H5 缺少可交互脚本或内容过短")
    if fakedoor.get("interactive") is not True:
        reasons.append("fakedoor.interactive：必须为 true，假门页要能点击")
    measured = fakedoor.get("measured_results")
    measured_ok = measured == "pending" or (
        isinstance(measured, dict)
        and measured.get("status") == "measured"
        and _nonempty(str(measured.get("source") or ""))
    )
    if not measured_ok:
        reasons.append("fakedoor.measured_results：没有真实外测时必须是 pending，禁止编造 CTR")
    return reasons


def compliance_field_reasons(compliance: Any, platform: str = "cross_platform") -> List[str]:
    """Field reasons for the tracking spec. Unused IDFA or AD_ID adds nothing."""
    from backend.app.services.profile_guard import covers_android, covers_ios

    if not isinstance(compliance, dict):
        return ["compliance：缺少广告追踪与受众声明"]
    reasons: List[str] = []
    uses_idfa = compliance.get("uses_idfa")
    uses_ad_id = compliance.get("uses_ad_id")
    if not _is_bool(uses_idfa):
        reasons.append("compliance.uses_idfa：必须是布尔值")
    if not _is_bool(uses_ad_id):
        reasons.append("compliance.uses_ad_id：必须是布尔值")
    if uses_idfa is True and covers_ios(platform):
        if not _nonempty(compliance.get("att_copy")):
            reasons.append("compliance.att_copy：使用 IDFA 时必须给出授权弹窗文案")
        if not _nonempty(compliance.get("att_denied_fallback")):
            reasons.append("compliance.att_denied_fallback：使用 IDFA 时必须给出拒绝后的降级")
    if uses_ad_id is True and covers_android(platform):
        if compliance.get("ad_id_permission_declared") is not True:
            reasons.append("compliance.ad_id_permission_declared：使用 AD_ID 时必须声明权限")
        age = compliance.get("min_audience_age")
        if not isinstance(age, int) or isinstance(age, bool) or age < 13:
            reasons.append("compliance.min_audience_age：使用 AD_ID 时必须声明最低受众年龄且不低于 13")
        if not _nonempty(compliance.get("ad_id_opt_out_fallback")):
            reasons.append("compliance.ad_id_opt_out_fallback：用户停用广告标识符后必须有降级")
    return reasons


def _validate_stage05(data: Dict[str, Any], platform: str) -> List[str]:
    reasons: List[str] = []
    views = data.get("views")
    if not isinstance(views, list) or not views or not all(_VIEW_ID.fullmatch(str(item) or "") for item in views):
        reasons.append("views：列出本版视图编号，例如 V-01")
    criteria = data.get("acceptance_criteria")
    if (
        not isinstance(criteria, list)
        or not criteria
        or not all(_AC_ID.fullmatch(str(item) or "") for item in criteria)
    ):
        reasons.append("acceptance_criteria：列出验收编号，例如 AC-01")
    events = data.get("event_dictionary")
    if not isinstance(events, list) or not events:
        reasons.append("event_dictionary：列出埋点事件")
    else:
        for index, event in enumerate(events):
            if not isinstance(event, dict) or not _nonempty(str(event.get("id") or "")) or not _nonempty(str(event.get("name") or "")):
                reasons.append(f"event_dictionary[{index}]：需要 id 和 name")
                break
    reasons.extend(compliance_field_reasons(data.get("compliance"), platform))
    return reasons


def _validate_stage06(
    data: Dict[str, Any],
    platform: str,
    root: Optional[Path] = None,
    upstream_views: Optional[List[str]] = None,
) -> List[str]:
    from backend.app.services.design_bundle import upstream_prd_views, validate_design_bundle

    views = upstream_views if upstream_views is not None else upstream_prd_views(root)
    return validate_design_bundle(root, data.get("design"), platform, views)


def _validate_stage07(data: Dict[str, Any], client_zero_inference: bool) -> List[str]:
    reasons: List[str] = []
    eng = data.get("engineering")
    if not isinstance(eng, dict):
        return ["engineering：缺少研发架构对象"]
    cov = eng.get("coverage_percent")
    if not _is_number(cov):
        reasons.append("engineering.coverage_percent：缺少核心单测覆盖率")
    elif cov < 80.0:
        reasons.append(f"engineering.coverage_percent：单测覆盖率 {cov}% 低于 80%")
    zero_inf = eng.get("zero_client_inference")
    if client_zero_inference and zero_inf is not True:
        reasons.append("engineering.zero_client_inference：当前 Profile 要求客户端零推理成本，必须为 true")
    return reasons


def _validate_stage08(data: Dict[str, Any]) -> List[str]:
    reasons: List[str] = []
    qa = data.get("quality")
    if not isinstance(qa, dict):
        return ["quality：缺少质量验收对象"]
    p0 = qa.get("open_p0")
    p1 = qa.get("open_p1")
    if not isinstance(p0, int) or isinstance(p0, bool) or p0 != 0:
        reasons.append(f"quality.open_p0：未关闭 P0 缺陷 ({p0})，必须为 0")
    if not isinstance(p1, int) or isinstance(p1, bool) or p1 != 0:
        reasons.append(f"quality.open_p1：未关闭 P1 缺陷 ({p1})，必须为 0")
    return reasons


def _validate_stage09(data: Dict[str, Any]) -> List[str]:
    reasons: List[str] = []
    rel = data.get("release")
    if not isinstance(rel, dict):
        return ["release：缺少发布提审配置对象"]
    if rel.get("compliance_checked") is not True:
        reasons.append("release.compliance_checked：商店合规自检必须为 true")
    if rel.get("has_remote_killswitch") is not True:
        reasons.append("release.has_remote_killswitch：必须具备远程降级开关 (Remote Config)")
    if not _nonempty(rel.get("rollback_plan")):
        reasons.append("release.rollback_plan：必须包含清晰的回滚预案")
    return reasons


def _validate_stage10(data: Dict[str, Any]) -> List[str]:
    reasons: List[str] = []
    acq = data.get("acquisition")
    if not isinstance(acq, dict):
        return ["acquisition：缺少获客方案对象"]
    ecac = acq.get("ecac_usd")
    limit = acq.get("ecac_limit_usd")
    if not _is_number(ecac) or ecac < 0:
        reasons.append("acquisition.ecac_usd：缺少或非法的预估获客成本")
    if not _is_number(limit) or limit < 0:
        reasons.append("acquisition.ecac_limit_usd：缺少或非法的获客熔断线")
    elif _is_number(ecac) and ecac > limit:
        reasons.append(f"acquisition.ecac_usd：预计获客成本 {ecac} 超过熔断线 {limit}")
    channels = acq.get("channels")
    if not isinstance(channels, list) or not channels:
        reasons.append("acquisition.channels：必须列出投放获客渠道")
    return reasons


def _validate_stage11(data: Dict[str, Any]) -> List[str]:
    reasons: List[str] = []
    ret = data.get("retention")
    if not isinstance(ret, dict):
        return ["retention：缺少运营留存对象"]
    for day in ("d1_retention", "d7_retention", "d30_retention"):
        val = ret.get(day)
        if not _is_number(val) or val < 0:
            reasons.append(f"retention.{day}：缺少或非法的留存百分比")
    items = ret.get("backlog_items") or ret.get("backlog_recommendations")
    if not isinstance(items, list) or not items:
        reasons.append("retention.backlog_items：必须列出下个迭代的 Backlog 需求建议")
    return reasons


def validate_manifest(
    manifest: Dict[str, Any],
    root: Optional[Path] = None,
    texts: Optional[List[str]] = None,
    platform: str = "cross_platform",
    client_zero_inference: bool = True,
) -> List[str]:
    """Field-level reasons across all 11 stages. Empty means the manifest and its referenced files are usable."""
    texts = texts or []
    reasons: List[str] = []
    if str(manifest.get("contract_version")) != CONTRACT_VERSION:
        reasons.append("contract_version：必须是 1")
    code = stage_code(manifest.get("stage"))
    if code not in CONTRACT_STAGES:
        reasons.append(f"stage：工序代码 {code} 不在支持的 01~11 范围内")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        reasons.append("artifacts：至少列出一份正文或入口文件")
    else:
        for index, item in enumerate(artifacts):
            if not isinstance(item, dict) or not _nonempty(str(item.get("role") or "")) or not _nonempty(str(item.get("path") or "")):
                reasons.append(f"artifacts[{index}]：需要 role 和 path")
                continue
            path = str(item["path"]).strip()
            if root is None:
                if path.startswith(("/", "\\")) or ".." in Path(path).parts:
                    reasons.append(f"artifacts[{index}].path：必须留在本工序目录内")
                continue
            resolved = _confined(root, path)
            if resolved is None:
                reasons.append(f"artifacts[{index}].path：必须留在本工序目录内")
            elif not resolved.is_file():
                reasons.append(f"artifacts[{index}].path：未找到 {path}")
    flags = manifest.get("risk_flags")
    if not isinstance(flags, dict):
        reasons.append("risk_flags：必须是对象")
    else:
        for key in RISK_FLAG_KEYS:
            if not _is_bool(flags.get(key)):
                reasons.append(f"risk_flags.{key}：必须是布尔值")

    # Stage-specific validations
    if code == "01":
        reasons.extend(_validate_stage01(manifest))
    elif code == "02":
        reasons.extend(_validate_stage02(manifest))
    elif code == "03":
        reasons.extend(_validate_stage03(manifest))
    elif code == "04":
        reasons.extend(_validate_fakedoor(manifest.get("fakedoor"), root, texts))
    elif code == "05":
        reasons.extend(_validate_stage05(manifest, platform))
    elif code == "06":
        reasons.extend(_validate_stage06(manifest, platform, root))
    elif code == "07":
        reasons.extend(_validate_stage07(manifest, client_zero_inference))
    elif code == "08":
        reasons.extend(_validate_stage08(manifest))
    elif code == "09":
        reasons.extend(_validate_stage09(manifest))
    elif code == "10":
        reasons.extend(_validate_stage10(manifest))
    elif code == "11":
        reasons.extend(_validate_stage11(manifest))

    return reasons


def tracking_findings(manifest: Dict[str, Any], platform: str) -> List[Dict[str, Any]]:
    """Compliance findings from the manifest. Unused tracking adds no item."""
    compliance = manifest.get("compliance")
    if not isinstance(compliance, dict):
        return [{
            "category": "platform_policy",
            "item": "compliance",
            "severity": "medium",
            "passed": False,
            "advice": "compliance：缺少广告追踪与受众声明",
        }]
    findings: List[Dict[str, Any]] = []
    for reason in compliance_field_reasons(compliance, platform):
        if reason.startswith("compliance.uses_"):
            findings.append({
                "category": "platform_policy",
                "item": reason.split("：", 1)[0],
                "severity": "medium",
                "passed": False,
                "advice": reason,
            })
    uses_idfa = compliance.get("uses_idfa") is True
    uses_ad_id = compliance.get("uses_ad_id") is True
    from backend.app.services.profile_guard import covers_android, covers_ios

    if uses_idfa and covers_ios(platform):
        missing = [
            reason for reason in compliance_field_reasons(compliance, platform)
            if reason.startswith("compliance.att_")
        ]
        findings.append({
            "category": "platform_policy",
            "item": "Apple App Tracking Transparency (ATT) 弹窗规格",
            "severity": "medium" if missing else "info",
            "passed": not missing,
            "advice": (
                "ATT 授权文案与拒绝后的降级写在清单 compliance 里。"
                if not missing else "；".join(missing)
            ),
        })
    if uses_ad_id and covers_android(platform):
        missing = [
            reason for reason in compliance_field_reasons(compliance, platform)
            if reason.startswith("compliance.ad_id_") or reason.startswith("compliance.min_audience_age")
        ]
        findings.append({
            "category": "platform_policy",
            "item": "Google Play Advertising ID (AD_ID) 权限声明与家庭政策",
            "severity": "medium" if missing else "info",
            "passed": not missing,
            "advice": (
                "AD_ID 权限、最低受众年龄与停用后的降级写在清单 compliance 里。"
                if not missing else "；".join(missing)
            ),
        })
    return findings
