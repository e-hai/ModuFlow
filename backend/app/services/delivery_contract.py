"""Structured handoff across all 11 stages (01 to 11).

The checker reads delivery.manifest.json field by field. A stage directory
without that file keeps the existing prose checks.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

MANIFEST_FILENAME = "delivery.manifest.json"
CONTRACT_VERSION = "1"
CONTRACT_STAGES = {f"{i:02d}" for i in range(1, 11)}

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

_VIEW_ID = re.compile(r"[a-z][a-z0-9_]{0,31}\Z")
_AC_ID = re.compile(r"AC-\d{2}\Z")
_FONT_LITERAL = re.compile(
    r"(?:font-size|fontSize|textSize)\s*[:=]\s*(\d+(?:\.\d+)?)|\.font\(\.system\(size:\s*(\d+(?:\.\d+)?)",
    re.I,
)
_SPACE_LITERAL = re.compile(
    r"(?:\bpadding\b|\bmargin\b|\bgap\b)(?:Horizontal|Vertical|Top|Bottom|Start|End|Left|Right)?"
    r"\s*[:=(]\s*(\d+(?:\.\d+)?)",
    re.I,
)

DEMO_ACCEPTANCE: List[Dict[str, str]] = [
    {
        "id": "AC-01",
        "view_id": "home",
        "given": "用户在 home 首页",
        "when": "选择模板并点击生成",
        "then": "10 秒内进入 result 结果页",
    },
    {
        "id": "AC-02",
        "view_id": "result",
        "given": "用户在 result 结果页",
        "when": "点击保存",
        "then": "作品出现在 history 历史页",
    },
]
DEMO_SCREENS: List[Dict[str, str]] = [
    {"view_id": "home", "path": "src/home.kt"},
    {"view_id": "editor", "path": "src/editor.kt"},
    {"view_id": "result", "path": "src/result.kt"},
    {"view_id": "history", "path": "src/history.kt"},
]
DEMO_APP = """def run(ac):
    if ac == \"AC-01\":
        view = \"home\"
        view = \"result\"
        return view
    if ac == \"AC-02\":
        view = \"result\"
        view = \"history\"
        return view
    raise SystemExit(\"未知验收\")
"""
TEST_PACKAGE_REL = "dist/app-test.zip"
RELEASE_PACKAGE_REL = "dist/app-release.zip"
TEST_PASSED_MARKER = ".moduflow_test_package_passed"
RELEASE_PENDING_REASON = "正式安装包尚未产出"
_APP_RUNNER = """import importlib.util, sys
path, ac = sys.argv[1], sys.argv[2]
spec = importlib.util.spec_from_file_location("mf_stage06_app", path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
run = getattr(mod, "run", None)
if not callable(run):
    raise SystemExit("应用入口没有 run(ac)")
view = run(ac)
if not isinstance(view, str) or not view.strip():
    raise SystemExit("run(ac) 必须返回页面 id")
print(view.strip())
"""


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
        f"artifacts 用 role 和 path 指向 `{filename}`，路径必须留在本工序目录内。",
        "修订时清单和正文一起改，只改长文不算完成。",
        "risk_flags 的 payment、privacy、user_data、encryption、lead_permissions、public_statement、data_dictionary 都写布尔值。红级只认这些字段。",
    ]
    if code == "01":
        lines.append(
            "market_research 必须包含 market、demand_definition、monthly_search_volume、target_capture_rate、"
            "blended_arpu_usd、annual_target_installs、first_year_som_usd、citations、source 和 verdict。"
            "年安装量等于月搜索量 × 12 × 取得比例，首年盘子再乘客单价。"
            "citations 分别指向月搜索量、取得比例、客单价的摘录。取得比例没有原句时 basis 写 assumption。"
        )
    elif code == "02":
        lines.append(
            "unit_economics 必须包含 organic_share、paid_cpi_usd、ad_arpu_usd、iap_conversion_rate、"
            "iap_net_arppu_usd、blended_cac_usd、ltv_180d_usd、ltv_cac_ratio（≥3.0）以及 pricing_tiers。"
            "全平台价格阶梯以此清单为唯一真理源。"
        )
    elif code == "03":
        lines.append(
            "direction 必须包含 uvp、target_audience、moscow（含 must 与 wont 数组）以及 hypotheses。"
            "每条假设含 id、hypothesis，并用 validation_stage 写明在哪一步验证。至少含 H1。"
        )

    elif code == "04":
        lines.append(
            "views 每项含 id 和 name。id 是小写英文短名，用来命名 screens/{id}.html，也用于跳转；"
            "name 只解释这一页，不参与路径。acceptance_criteria 每项含 id（AC-01）、view_id（视图索引里的 id）、given、when、then。"
            "event_dictionary 每项含 id 和 name。"
            "正文第 0 章用四列表：上线版本（如 1.0.0）、稿次（只写 r1、r2）、来源（工序 03、变更单或承接）、变更。"
            "同一上线版本里改稿只加稿次，不要写成 1.0.1。"
        )
        lines.append(
            "compliance 写 uses_idfa、att_copy、att_denied_fallback、uses_ad_id、"
            "ad_id_permission_declared、min_audience_age、ad_id_opt_out_fallback。"
            "不使用 IDFA 或 AD_ID 时把对应 uses_* 标为 false，不要靠正文里出现 ATT 这三个字母。"
        )
    elif code == "05":
        lines.append(
            "design 是设计交付包清单，必须包含 platform、entry（index.html 设计工作台）、tokens_path（tokens.json）、"
            "screens（每个工序 04 视图一项：view_id 等于该视图 id、path 为 screens/{id}.html、platforms）和 icons（assets/icons/*.svg 路径列表）。"
            "每张画板必须有 iOS/Android 设备外框（data-device、data-safe-top、data-safe-bottom）、四态面板（data-state）、"
            "可点击元素的 data-hit 热区标注，颜色只能来自 tokens.json，零外部依赖。"
            "安全区标注必须有对应的样式高度，热区标注必须有不小于该尺寸的 min-width 和 min-height。"
            "空态和错态面板里要有可点击的操作。"
            "iOS 顶部 ≥ 71pt、底部 ≥ 34pt、触控 ≥ 44pt；Android 状态栏 ≥ 24dp、触控 ≥ 48dp。"
        )
    elif code == "06":
        lines.append(
            "engineering 必须包含 coverage_percent（核心单测 ≥ 80）以及 zero_client_inference（按 profile 声明端侧零推理）。"
            "screens 里每个工序 04 视图 id 对应一个本工序目录内的实现文件。"
            "tests 里每条验收对应一个测试文件，文件里写明编号和该条 Then，command 是 python、gradlew、swift 或 xcodebuild。"
            "app 指向应用入口，定义 run(ac) 并返回跑完后的页面 id。"
            "packages.test 是测试安装包。正式安装包 packages.release 要等工序 07 测完测试包后再交。"
            "代码和说明里的颜色、字号、间距必须来自工序 05 的 tokens.json。"
        )
    elif code == "07":
        lines.append(
            "quality 必须包含 open_p0（必须为 0）、open_p1（必须为 0）、test_cases_total 与 test_cases_passed。"
            "放行时先用工序 06 的测试安装包跑验收，通过后再用正式安装包做一次启动验收。"
            "测试文件里要有对应的 Then，退出码不是 0，或跑完停在的页面不在 Then 里，都不能把 open_p0 写成 0。"
        )
    elif code == "08":
        lines.append(
            "release 必须包含 store_targets、compliance_checked（true）、has_remote_killswitch（true）与 rollback_plan（回滚预案）。"
        )
    elif code == "09":
        lines.append(
            "acquisition 必须包含 ecac_usd、ecac_limit_usd（熔断线）、channels 与 daily_budget_usd。"
        )
    elif code == "10":
        lines.append(
            "retention 必须包含 d1_retention、d7_retention、d30_retention 与 backlog_items（增量需求建议）。"
        )
    return " ".join(lines)


def build_stage_manifest(
    module_code: str,
    report_path: str,
    platform: str = "cross_platform",
    views: Optional[List[str]] = None,
    release_package: bool = False,
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
                "market": "美国",
                "demand_definition": "演示品类",
                "monthly_search_volume": volume,
                "target_capture_rate": rate,
                "blended_arpu_usd": arpu,
                "annual_target_installs": annual,
                "first_year_som_usd": som,
                "citations": {
                    "monthly_search_volume": {"basis": "assumption"},
                    "target_capture_rate": {"basis": "assumption"},
                    "blended_arpu_usd": {"basis": "assumption"},
                },
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
                    {"id": "H1", "hypothesis": "目标用户愿意为无广告体验与高质导出付费", "validation_stage": "10"},
                    {"id": "H2", "hypothesis": "次日留存不低于品类基准", "validation_stage": "10"},
                ],
            },
        }

    elif code == "04":
        data = {
            "contract_version": CONTRACT_VERSION,
            "stage": "04",
            "artifacts": [{"role": "prd", "path": report_path}],
            "risk_flags": flags,
            "views": [
                {"id": "home", "name": "首页"},
                {"id": "editor", "name": "生成页"},
                {"id": "result", "name": "结果页"},
                {"id": "history", "name": "历史页"},
            ],
            "acceptance_criteria": [dict(item) for item in DEMO_ACCEPTANCE],
            "event_dictionary": [
                {"id": "E-01", "name": "generate_start"},
                {"id": "E-02", "name": "generate_success"},
                {"id": "E-03", "name": "save_result"},
            ],
            "compliance": {"uses_idfa": False, "uses_ad_id": False},
        }
    elif code == "05":
        from backend.app.services.design_bundle_sim import design_manifest_block

        artifacts_06 = [
            {"role": "design_spec", "path": report_path},
            {"role": "design_workbench", "path": "index.html"},
            {"role": "design_tokens", "path": "tokens.json"},
        ]
        view_list = views or ["home", "editor", "result", "history"]
        artifacts_06 += [{"role": "design_screen", "path": f"screens/{view}.html"} for view in view_list]
        data = {
            "contract_version": CONTRACT_VERSION,
            "stage": "05",
            "artifacts": artifacts_06,
            "risk_flags": flags,
            "design": design_manifest_block(platform, view_list),
        }
    elif code == "06":
        data = {
            "contract_version": CONTRACT_VERSION,
            "stage": "06",
            "artifacts": [{"role": "architecture_spec", "path": report_path}],
            "risk_flags": flags,
            "engineering": {
                "coverage_percent": 85.0,
                "zero_client_inference": True,
                "modules": ["auth", "core_pipeline", "storage_sync"],
                "screens": [dict(item) for item in DEMO_SCREENS],
                "app": "app.py",
                "packages": _demo_packages(release_package),
                "tests": [
                    {"ac": "AC-01", "path": "tests/test_ac_01.py", "command": ["python", "tests/test_ac_01.py"]},
                    {"ac": "AC-02", "path": "tests/test_ac_02.py", "command": ["python", "tests/test_ac_02.py"]},
                ],
            },
        }
    elif code == "07":
        data = {
            "contract_version": CONTRACT_VERSION,
            "stage": "07",
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
    elif code == "08":
        data = {
            "contract_version": CONTRACT_VERSION,
            "stage": "08",
            "artifacts": [{"role": "release_notes", "path": report_path}],
            "risk_flags": flags,
            "release": {
                "store_targets": ["app_store", "google_play"],
                "compliance_checked": True,
                "has_remote_killswitch": True,
                "rollback_plan": "如遇严重缺陷，通过 Remote Config 关闭新特性，立即回滚至上一稳定版本。",
            },
        }
    elif code == "09":
        data = {
            "contract_version": CONTRACT_VERSION,
            "stage": "09",
            "artifacts": [{"role": "marketing_plan", "path": report_path}],
            "risk_flags": flags,
            "acquisition": {
                "ecac_usd": 1.85,
                "ecac_limit_usd": 2.5,
                "channels": ["meta_ads", "google_search"],
                "daily_budget_usd": 150.0,
            },
        }
    elif code == "10":
        data = {
            "contract_version": CONTRACT_VERSION,
            "stage": "10",
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


def read_stage_file(storage_rel_path: Optional[str], name: str) -> str:
    """Read one file next to a stage artifact. `name` is a single path segment."""
    if not storage_rel_path or not name or name != Path(name).name:
        return ""
    workspace = _workspace_root()
    root = (workspace / storage_rel_path).resolve()
    if workspace != root and workspace not in root.parents:
        return ""
    directory = root if root.is_dir() else root.parent
    path = directory / name
    if not path.is_file():
        return ""
    try:
        if path.stat().st_size > 200_000:
            return ""
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


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

def _stage01_product(mr: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    try:
        volume = int(float(mr["monthly_search_volume"]))
        rate = float(mr["target_capture_rate"])
        arpu = float(mr["blended_arpu_usd"])
    except (KeyError, TypeError, ValueError):
        return None
    if volume < 0 or arpu < 0 or rate < 0 or rate > 1:
        return None
    annual = int(volume * 12 * rate)
    return {
        "monthly_search_volume": volume,
        "target_capture_rate": rate,
        "blended_arpu_usd": arpu,
        "annual_target_installs": annual,
        "first_year_som_usd": round(annual * arpu, 2),
    }


def _source_rows(root: Optional[Path]) -> Optional[List[Dict[str, Any]]]:
    if root is None:
        return None
    path = Path(root) / "sources" / "index.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def _demo_texts(texts: Optional[List[str]]) -> bool:
    return any("演示稿" in (text or "") for text in texts or [])


def _excerpt_body(root: Path, url: str, rows: List[Dict[str, Any]]) -> str:
    for row in rows:
        if str(row.get("url") or "") != url:
            continue
        rel = str(row.get("path") or "")
        path = _confined(root, rel) if rel else None
        if path is None or not path.is_file():
            return ""
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""
    return ""


def _number_in_excerpt(value: float, text: str, kind: str) -> bool:
    compact = (text or "").replace(",", "").replace(" ", "")
    if kind == "rate":
        decimal = f"{value:.4f}".rstrip("0").rstrip(".")
        percent = f"{value * 100:.2f}".rstrip("0").rstrip(".")
        return bool(decimal) and (decimal in compact or f"{percent}%" in text or f"{percent}％" in text)
    if kind == "money":
        raw = f"{value:.2f}".rstrip("0").rstrip(".")
    else:
        raw = str(int(value))
    if raw and raw in compact:
        return True
    if value >= 10000 and float(value).is_integer() and int(value) % 10000 == 0:
        return f"{int(value) // 10000}万" in text
    return False


def stage01_snapshot(mr: Dict[str, Any], rows: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """确认单用的工序 01 数字。首年盘子用乘积，不用稿子里另写的数。"""
    product = _stage01_product(mr) or {}
    citations = mr.get("citations") if isinstance(mr.get("citations"), dict) else {}
    by_url = {str(row.get("url")): row for row in rows or [] if isinstance(row, dict) and row.get("url")}
    basis: Dict[str, str] = {}
    labels: Dict[str, str] = {}
    for key in ("monthly_search_volume", "target_capture_rate", "blended_arpu_usd"):
        item = citations.get(key) if isinstance(citations.get(key), dict) else {}
        raw = str(item.get("basis") or "")
        if raw in ("assumption", "excerpt"):
            basis[key] = raw
        row = by_url.get(str(item.get("url") or ""))
        labels[key] = str((row or {}).get("source_name") or item.get("source_name") or "")
    return {
        "monthly_search_volume": product.get("monthly_search_volume", mr.get("monthly_search_volume")),
        "target_capture_rate": product.get("target_capture_rate", mr.get("target_capture_rate")),
        "blended_arpu_usd": product.get("blended_arpu_usd", mr.get("blended_arpu_usd")),
        "annual_target_installs": product.get("annual_target_installs", mr.get("annual_target_installs")),
        "first_year_som_usd": product.get("first_year_som_usd", mr.get("first_year_som_usd")),
        "source": str(mr.get("source") or ""),
        "verdict": mr.get("verdict"),
        "market": str(mr.get("market") or ""),
        "demand_definition": str(mr.get("demand_definition") or ""),
        "input_basis": basis,
        "citation_labels": labels,
        "capture_rate_basis": basis.get("target_capture_rate") or "",
    }


def stage01_excerpt_reasons(
    mr: Dict[str, Any],
    root: Optional[Path],
    texts: Optional[List[str]] = None,
) -> List[str]:
    """有摘录索引、且不是演示稿时，月搜索量和客单价必须对上原句。"""
    if _demo_texts(texts):
        return []
    rows = _source_rows(root)
    if rows is None or root is None:
        return []
    reasons: List[str] = []
    if not _nonempty(str(mr.get("market") or "")):
        reasons.append("market_research.market：要写明哪个国家或地区")
    if not _nonempty(str(mr.get("demand_definition") or "")):
        reasons.append("market_research.demand_definition：要写明哪个词或哪个品类")
    product = _stage01_product(mr)
    if product is None:
        return reasons
    citations = mr.get("citations") if isinstance(mr.get("citations"), dict) else {}
    checks = (
        ("monthly_search_volume", "月搜索量", "volume", False),
        ("blended_arpu_usd", "客单价", "money", False),
        ("target_capture_rate", "取得比例", "rate", True),
    )
    for key, label, kind, allow_assumption in checks:
        item = citations.get(key) if isinstance(citations.get(key), dict) else None
        if item is None:
            reasons.append(f"market_research.citations.{key}：缺少出处")
            continue
        basis = str(item.get("basis") or "")
        if allow_assumption and basis == "assumption":
            continue
        if basis != "excerpt":
            reasons.append(f"market_research.citations.{key}：{label}必须来自摘录")
            continue
        url = str(item.get("url") or "")
        body = _excerpt_body(root, url, rows)
        if not url or url not in body or not _number_in_excerpt(float(product[key]), body, kind):
            reasons.append(f"market_research.{key}：{label}在摘录原句里没有出现")
    return reasons


def _validate_stage01(
    data: Dict[str, Any],
    root: Optional[Path] = None,
    texts: Optional[List[str]] = None,
) -> List[str]:
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
    if not _nonempty(str(mr.get("market") or "")):
        reasons.append("market_research.market：要写明哪个国家或地区")
    if not _nonempty(str(mr.get("demand_definition") or "")):
        reasons.append("market_research.demand_definition：要写明哪个词或哪个品类")
    citations = mr.get("citations")
    if not isinstance(citations, dict):
        reasons.append("market_research.citations：要分别标明月搜索量、取得比例和客单价的出处")
    else:
        for key in ("monthly_search_volume", "target_capture_rate", "blended_arpu_usd"):
            if not isinstance(citations.get(key), dict):
                reasons.append(f"market_research.citations.{key}：缺少出处")
    product = _stage01_product(mr)
    if product is not None:
        if _is_number(mr.get("annual_target_installs")) and int(mr["annual_target_installs"]) != product["annual_target_installs"]:
            reasons.append(
                "market_research.annual_target_installs："
                f"写的是 {mr.get('annual_target_installs')}，按月搜索量 × 12 × 取得比例算出的是 {product['annual_target_installs']}"
            )
        if _is_number(mr.get("first_year_som_usd")):
            from backend.app.services.deliverable_audit import _som_disagrees

            if _som_disagrees(float(mr["first_year_som_usd"]), float(product["first_year_som_usd"])):
                reasons.append(
                    "market_research.first_year_som_usd："
                    f"写的是 {mr.get('first_year_som_usd')}，按三个输入算出的是 {product['first_year_som_usd']}"
                )
        if not _demo_texts(texts):
            from backend.app.services.deliverable_audit import _som_disagrees, _stated_som_amounts

            for text in texts or []:
                for stated in _stated_som_amounts(text):
                    if _som_disagrees(stated, float(product["first_year_som_usd"])):
                        reasons.append(
                            f"正文里的首年盘子写的是 {stated:,.0f} 美元，按月搜索量、取得比例和客单价算出的是 {product['first_year_som_usd']:,.2f} 美元。请把正文改成算出的数。"
                        )
                        break
    reasons.extend(stage01_excerpt_reasons(mr, root, texts))
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
    from backend.app.services.deliverable_audit import _stage02_mismatch, stage02_snapshot

    snap = stage02_snapshot(ue)
    if snap:
        reasons.extend(_stage02_mismatch(ue, snap))
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
    if not isinstance(moscow, dict) or not isinstance(moscow.get("must"), list) or not any(
        _nonempty(str(item)) for item in moscow.get("must") or []
    ):
        reasons.append("direction.moscow.must：必须包含 MVP 交付范围清单")
    if not _nonempty(direction.get("target_audience")):
        reasons.append("direction.target_audience：缺少给谁做")
    wont = moscow.get("wont") if isinstance(moscow, dict) else None
    if not isinstance(wont, list) or not any(_nonempty(str(item)) for item in wont):
        reasons.append("direction.moscow.wont：明确不做至少一项")
    hypotheses = direction.get("hypotheses")
    has_h1 = False
    if isinstance(hypotheses, list) and hypotheses:
        for index, hyp in enumerate(hypotheses):
            if isinstance(hyp, dict) and "H1" in str(hyp.get("id") or ""):
                has_h1 = True
            elif isinstance(hyp, str) and "H1" in hyp:
                has_h1 = True
            if isinstance(hyp, dict):
                if not _nonempty(hyp.get("hypothesis")):
                    reasons.append(f"direction.hypotheses[{index}]：缺少假设内容")
                if not _nonempty(hyp.get("validation_stage")):
                    reasons.append(f"direction.hypotheses[{index}]：缺少验证方式")
            elif _nonempty(str(hyp)):
                reasons.append(f"direction.hypotheses[{index}]：缺少验证方式")
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


def _acceptance_reasons(criteria: Any, view_ids: set) -> List[str]:
    """每条验收要写明编号、所属视图和 Given / When / Then。"""
    if not isinstance(criteria, list) or not criteria:
        return ["acceptance_criteria：每条验收要有 id、view_id、given、when、then"]
    reasons: List[str] = []
    seen: List[str] = []
    for index, item in enumerate(criteria):
        prefix = f"acceptance_criteria[{index}]"
        if not isinstance(item, dict):
            reasons.append(f"{prefix}：需要 id、view_id、given、when、then")
            continue
        ac = str(item.get("id") or "").strip()
        view_id = str(item.get("view_id") or "").strip()
        if not _AC_ID.fullmatch(ac):
            reasons.append(f"{prefix}.id：必须是 AC-xx")
        elif ac in seen:
            reasons.append(f"{prefix}.id：{ac} 重复")
        else:
            seen.append(ac)
        if not _VIEW_ID.fullmatch(view_id):
            reasons.append(f"{prefix}.view_id：必须是视图索引里的 id")
        elif view_ids and view_id not in view_ids:
            reasons.append(f"{prefix}.view_id：{view_id} 不在视图索引里")
        for key in ("given", "when", "then"):
            if not _nonempty(str(item.get(key) or "")):
                reasons.append(f"{prefix}.{key}：不能为空")
    return reasons


def _validate_stage04(data: Dict[str, Any], platform: str) -> List[str]:
    reasons: List[str] = []
    views = data.get("views")
    seen: set = set()
    if not isinstance(views, list) or not views:
        reasons.append('views：每项含英文 id 和 name，例如 {"id": "home", "name": "首页"}')
    else:
        for index, item in enumerate(views):
            if not isinstance(item, dict):
                reasons.append(f"views[{index}]：需要 id 和 name")
                continue
            vid = str(item.get("id") or "").strip()
            if not _VIEW_ID.fullmatch(vid):
                reasons.append(f"views[{index}].id：{vid or '(空)'} 必须是小写英文短名，用来命名文件")
            elif vid in seen:
                reasons.append(f"views[{index}].id：{vid} 重复")
            else:
                seen.add(vid)
            if not _nonempty(str(item.get("name") or "")):
                reasons.append(f"views[{index}].name：用来解释这一页，不能为空")
    reasons.extend(_acceptance_reasons(data.get("acceptance_criteria"), seen))
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


def _validate_stage05(
    data: Dict[str, Any],
    platform: str,
    root: Optional[Path] = None,
    upstream_views: Optional[List[str]] = None,
) -> List[str]:
    from backend.app.services.design_bundle import upstream_prd_views, validate_design_bundle

    views = upstream_views if upstream_views is not None else upstream_prd_views(root)
    return validate_design_bundle(root, data.get("design"), platform, views)


def _validate_stage06(data: Dict[str, Any], client_zero_inference: bool, root: Optional[Path] = None) -> List[str]:
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
    reasons.extend(engineering_screen_reasons(eng.get("screens"), root))
    reasons.extend(engineering_test_reasons(eng.get("tests"), root))
    reasons.extend(engineering_app_reasons(eng, root))
    reasons.extend(engineering_package_reasons(eng, root))
    if root is not None:
        design_root = sibling_stage_dir(root, "05")
        reasons.extend(engineering_color_reasons(root, design_root))
        reasons.extend(engineering_measure_reasons(root, design_root))
    return reasons


_CODE_SUFFIXES = {".kt", ".kts", ".swift", ".xml", ".css", ".ts", ".tsx", ".js", ".jsx", ".m", ".mm", ".md"}
_SHELL_META = re.compile(r"[;&|`$<>\n]")
_TEST_TIMEOUT_SECONDS = 60
_SCAN_SKIP = {".git", "build", "node_modules", ".gradle", ".agents"}


def sibling_stage_dir(root: Optional[Path], stage: str) -> Optional[Path]:
    """同一迭代目录下，清单 stage 等于给定工序的兄弟目录。"""
    if root is None:
        return None
    parent = root.resolve().parent
    if not parent.is_dir():
        return None
    want = stage.zfill(2) if str(stage).isdigit() else str(stage)
    here = root.resolve()
    for sibling in sorted(path for path in parent.iterdir() if path.is_dir()):
        if sibling.resolve() == here:
            continue
        manifest = sibling / MANIFEST_FILENAME
        if not manifest.is_file():
            continue
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        code = stage_code(data.get("stage"))
        if code == want:
            return sibling
    return None


def design_bundle_file_gaps(root: Optional[Path]) -> List[str]:
    """工序 05 目录里 tokens.json 或清单上的画板文件缺失时，返回缺口说明。"""
    if root is None or not root.is_dir():
        return ["设计目录不存在"]
    manifest_path = root / MANIFEST_FILENAME
    design: Dict[str, Any] = {}
    if manifest_path.is_file():
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = None
        if isinstance(data, dict) and isinstance(data.get("design"), dict):
            design = data["design"]
    tokens_rel = str(design.get("tokens_path") or "tokens.json").strip() or "tokens.json"
    gaps: List[str] = []
    tokens = _confined(root, tokens_rel)
    if tokens is None or not tokens.is_file():
        gaps.append(f"令牌文件 {tokens_rel}")
    screens = design.get("screens") if isinstance(design.get("screens"), list) else []
    if design and not screens:
        gaps.append("设计清单没有画板")
    elif screens:
        for item in screens:
            if not isinstance(item, dict):
                gaps.append("设计清单有无法读取的画板")
                continue
            rel = str(item.get("path") or "").strip()
            path = _confined(root, rel)
            if path is None or not path.is_file():
                gaps.append(f"画板 {rel or '(空)'}")
    elif not (root / "screens").is_dir() or not any((root / "screens").glob("*.html")):
        gaps.append("画板")
    return gaps


def _sibling_manifest(root: Optional[Path], stage: str) -> Optional[Dict[str, Any]]:
    folder = sibling_stage_dir(root, stage)
    if folder is None:
        return None
    try:
        data = json.loads((folder / MANIFEST_FILENAME).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def acceptance_records_from(data: Any) -> List[Dict[str, str]]:
    """读出验收条目。旧清单里的纯编号仍保留 id，Then 为空。"""
    items = data.get("acceptance_criteria") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return []
    records: List[Dict[str, str]] = []
    for item in items:
        if isinstance(item, str):
            records.append({"id": item.strip(), "view_id": "", "given": "", "when": "", "then": ""})
            continue
        if not isinstance(item, dict):
            continue
        records.append({
            "id": str(item.get("id") or "").strip(),
            "view_id": str(item.get("view_id") or "").strip(),
            "given": str(item.get("given") or "").strip(),
            "when": str(item.get("when") or "").strip(),
            "then": str(item.get("then") or "").strip(),
        })
    return records


def acceptance_ids_near(root: Optional[Path]) -> List[str]:
    """工序 06 目录的兄弟工序 04 清单里的验收编号。"""
    found: List[str] = []
    for item in acceptance_records_from(_sibling_manifest(root, "04") or {}):
        if _AC_ID.fullmatch(item["id"]) and item["id"] not in found:
            found.append(item["id"])
    return found


def _then_by_ac(root: Optional[Path]) -> Dict[str, str]:
    found: Dict[str, str] = {}
    for item in acceptance_records_from(_sibling_manifest(root, "04") or {}):
        if _AC_ID.fullmatch(item["id"]) and item["then"] and item["id"] not in found:
            found[item["id"]] = item["then"]
    return found


def view_ids_near(root: Optional[Path]) -> List[str]:
    data = _sibling_manifest(root, "04")
    views = data.get("views") if isinstance(data, dict) else None
    if not isinstance(views, list):
        return []
    found: List[str] = []
    for item in views:
        vid = str(item.get("id") or "").strip() if isinstance(item, dict) else str(item or "").strip()
        if _VIEW_ID.fullmatch(vid) and vid not in found:
            found.append(vid)
    return found


def engineering_screen_reasons(screens: Any, root: Optional[Path]) -> List[str]:
    """每个工序 04 视图要有一个仍在工序 06 目录里的实现文件。没有上游视图时不查。"""
    required = view_ids_near(root)
    if not required:
        return []
    if not isinstance(screens, list):
        return ["engineering.screens：每个工序 04 视图要对应一个实现文件"]
    reasons: List[str] = []
    seen: List[str] = []
    for index, item in enumerate(screens):
        prefix = f"engineering.screens[{index}]"
        if not isinstance(item, dict):
            reasons.append(f"{prefix}：需要 view_id 和 path")
            continue
        vid = str(item.get("view_id") or "").strip()
        rel = str(item.get("path") or "").strip()
        if not _VIEW_ID.fullmatch(vid):
            reasons.append(f"{prefix}.view_id：必须是视图 id")
        elif vid not in required:
            reasons.append(f"{prefix}.view_id：{vid} 不是工序 04 的视图")
        elif vid in seen:
            reasons.append(f"engineering.screens：视图 {vid} 重复")
        else:
            seen.append(vid)
        path = _confined(root, rel) if root is not None else None
        if root is None:
            if not rel or Path(rel).is_absolute() or ".." in Path(rel).parts:
                reasons.append(f"{prefix}.path：必须留在本工序目录内")
        elif path is None or not path.is_file():
            reasons.append(f"{prefix}.path：未找到实现文件 {rel or '(空)'}")
    missing = [vid for vid in required if vid not in seen]
    if missing:
        reasons.append("engineering.screens：没有覆盖工序 04 的视图 " + "、".join(missing))
    return reasons


def engineering_test_reasons(tests: Any, root: Optional[Path]) -> List[str]:
    """每条已知验收编号要对应清单里的一个测试文件；给了目录就核对文件还在，并写上 Then。"""
    required = acceptance_ids_near(root)
    clauses = _then_by_ac(root)
    if not isinstance(tests, list):
        if required:
            return ["engineering.tests：每条验收编号要对应一个测试文件"]
        return []
    reasons: List[str] = []
    seen: List[str] = []
    for index, item in enumerate(tests):
        if not isinstance(item, dict):
            reasons.append(f"engineering.tests[{index}]：需要 ac、path 和 command")
            continue
        ac = str(item.get("ac") or "").strip()
        rel = str(item.get("path") or "").strip()
        if not _AC_ID.fullmatch(ac):
            reasons.append(f"engineering.tests[{index}].ac：必须是 AC-xx")
        elif ac in seen:
            reasons.append(f"engineering.tests：验收编号 {ac} 重复")
        else:
            seen.append(ac)
        reasons.extend(_command_reasons(index, item.get("command"), rel))
        path = _confined(root, rel) if root is not None else None
        if root is None:
            if not rel or Path(rel).is_absolute() or ".." in Path(rel).parts:
                reasons.append(f"engineering.tests[{index}].path：必须留在本工序目录内")
        elif path is None or not path.is_file():
            reasons.append(f"engineering.tests[{index}].path：未找到测试文件 {rel or '(空)'}")
        else:
            text = path.read_text(encoding="utf-8", errors="replace")
            if ac and not _ac_in_text(ac, text):
                reasons.append(f"engineering.tests[{index}]：测试文件没有写明 {ac}")
            clause = clauses.get(ac) or ""
            if clause and clause not in text:
                reasons.append(f"engineering.tests[{index}]：测试文件没有写上 {ac} 的 Then：{clause}")
    missing = [ac for ac in required if ac not in seen]
    if missing:
        reasons.append("engineering.tests：没有覆盖工序 04 的验收 " + "、".join(missing))
    return reasons


def _token_colors(tokens_file: Path) -> List[str]:
    from backend.app.services.design_bundle import HEX_RE, _norm_hex

    try:
        data = json.loads(tokens_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    colors = data.get("color") if isinstance(data, dict) else None
    if not isinstance(colors, dict):
        return []
    found: List[str] = []
    for value in colors.values():
        if isinstance(value, str) and HEX_RE.fullmatch(value.strip()):
            norm = _norm_hex(value.strip())
            if norm not in found:
                found.append(norm)
    return found


def engineering_color_reasons(code_root: Optional[Path], design_root: Optional[Path]) -> List[str]:
    """代码和说明里的十六进制颜色必须出现在工序 05 的 tokens.json。没有设计目录时不查。"""
    if code_root is None or design_root is None or not design_root.is_dir():
        return []
    tokens_file = design_root / "tokens.json"
    manifest = design_root / MANIFEST_FILENAME
    if manifest.is_file():
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = None
        design = data.get("design") if isinstance(data, dict) else None
        rel = str(design.get("tokens_path") or "").strip() if isinstance(design, dict) else ""
        resolved = _confined(design_root, rel) if rel else None
        if resolved is not None and resolved.is_file():
            tokens_file = resolved
    if not tokens_file.is_file():
        return ["工序 05 目录里没有 tokens.json"]
    allowed = set(_token_colors(tokens_file))
    if not allowed:
        return ["工序 05 的 tokens.json 没有颜色"]
    from backend.app.services.design_bundle import HEX_RE, _norm_hex

    stray: List[str] = []
    for _path, text in _iter_code_texts(code_root):
        for match in HEX_RE.finditer(text):
            color = _norm_hex(match.group(0))
            if color not in allowed and color not in stray:
                stray.append(color)
    if not stray:
        return []
    return ["研发交付使用了设计令牌之外的颜色 " + "、".join(stray[:6])]


def _iter_code_texts(root: Path):
    base = root.resolve()
    for path in sorted(base.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in _CODE_SUFFIXES or path.name.startswith("."):
            continue
        if any(part in _SCAN_SKIP for part in path.relative_to(base).parts):
            continue
        if path.name == MANIFEST_FILENAME:
            continue
        try:
            if path.stat().st_size > 200_000:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        yield path, text


def _tokens_file(design_root: Path) -> Optional[Path]:
    tokens_file = design_root / "tokens.json"
    manifest = design_root / MANIFEST_FILENAME
    if manifest.is_file():
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = None
        design = data.get("design") if isinstance(data, dict) else None
        rel = str(design.get("tokens_path") or "").strip() if isinstance(design, dict) else ""
        resolved = _confined(design_root, rel) if rel else None
        if resolved is not None and resolved.is_file():
            return resolved
    return tokens_file if tokens_file.is_file() else None


def _literal_numbers(pattern: re.Pattern, text: str) -> List[str]:
    found: List[str] = []
    for match in pattern.finditer(text or ""):
        raw = next((group for group in match.groups() if group), "")
        if raw and raw not in found:
            found.append(raw)
    return found


def _number_allowed(raw: str, allowed: set) -> bool:
    try:
        value = float(raw)
    except ValueError:
        return False
    return any(abs(value - item) < 1e-6 for item in allowed)


def _measure_sets(tokens_file: Path) -> tuple:
    try:
        data = json.loads(tokens_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set(), set()
    if not isinstance(data, dict):
        return set(), set()
    fonts: set = set()
    typography = data.get("typography")
    if isinstance(typography, dict):
        for value in typography.values():
            if isinstance(value, dict):
                for key in ("size", "line"):
                    if _is_number(value.get(key)):
                        fonts.add(float(value[key]))
            elif _is_number(value):
                fonts.add(float(value))
    spaces: set = set()
    spacing = data.get("spacing")
    if isinstance(spacing, dict):
        for value in spacing.values():
            if _is_number(value):
                spaces.add(float(value))
    return fonts, spaces


def engineering_measure_reasons(code_root: Optional[Path], design_root: Optional[Path]) -> List[str]:
    """代码和说明里写出的字号、间距必须出现在工序 05 的 tokens.json。没有设计目录时不查。"""
    if code_root is None or design_root is None or not design_root.is_dir():
        return []
    tokens_file = _tokens_file(design_root)
    if tokens_file is None:
        return []
    fonts, spaces = _measure_sets(tokens_file)
    stray_fonts: List[str] = []
    stray_spaces: List[str] = []
    saw_font = False
    saw_space = False
    for _path, text in _iter_code_texts(code_root):
        for raw in _literal_numbers(_FONT_LITERAL, text):
            saw_font = True
            if not _number_allowed(raw, fonts) and raw not in stray_fonts:
                stray_fonts.append(raw)
        for raw in _literal_numbers(_SPACE_LITERAL, text):
            saw_space = True
            if not _number_allowed(raw, spaces) and raw not in stray_spaces:
                stray_spaces.append(raw)
    reasons: List[str] = []
    if saw_font and not fonts:
        reasons.append("工序 05 的 tokens.json 没有字号")
    elif stray_fonts:
        reasons.append("研发交付使用了设计令牌之外的字号 " + "、".join(stray_fonts[:6]))
    if saw_space and not spaces:
        reasons.append("工序 05 的 tokens.json 没有间距")
    elif stray_spaces:
        reasons.append("研发交付使用了设计令牌之外的间距 " + "、".join(stray_spaces[:6]))
    return reasons


def _command_reasons(index: int, command: Any, path_rel: str) -> List[str]:
    prefix = f"engineering.tests[{index}].command"
    if not isinstance(command, list) or not command or not all(isinstance(part, str) and part.strip() for part in command):
        return [f"{prefix}：必须是非空的命令数组"]
    if any(_SHELL_META.search(part) for part in command):
        return [f"{prefix}：不能包含 shell 控制符"]
    exe = command[0]
    if exe in ("python", "python3"):
        if command[1:] != [path_rel]:
            return [f"{prefix}：python 只能运行该条测试文件"]
        return []
    if exe in ("gradlew", "./gradlew", "swift", "xcodebuild"):
        return []
    return [f"{prefix}：只能使用 python、gradlew、swift 或 xcodebuild"]


def _ac_in_text(ac: str, text: str) -> bool:
    return re.search(rf"(?<![A-Z0-9-]){re.escape(ac)}(?!\d)", text or "") is not None


def _resolve_test_command(command: List[str], root: Path) -> Optional[List[str]]:
    exe = command[0]
    if exe in ("python", "python3"):
        script = _confined(root, command[1])
        if script is None or not script.is_file():
            return None
        return [sys.executable, str(script)]
    if exe in ("gradlew", "./gradlew"):
        gradlew = _confined(root, "gradlew")
        if gradlew is None or not gradlew.is_file():
            return None
        return [str(gradlew), *command[1:]]
    if exe in ("swift", "xcodebuild"):
        return list(command)
    return None


def engineering_app_reasons(eng: Any, root: Optional[Path]) -> List[str]:
    """有工序 04 的 Then 时，工序 06 要留下可调用的应用入口。没有上游验收时不查。"""
    if not _then_by_ac(root):
        return []
    rel = "app.py"
    if isinstance(eng, dict) and str(eng.get("app") or "").strip():
        rel = str(eng.get("app")).strip()
    if root is None:
        if not rel or Path(rel).is_absolute() or ".." in Path(rel).parts:
            return ["engineering.app：必须留在本工序目录内"]
        return []
    path = _confined(root, rel)
    if path is None or not path.is_file():
        return [f"engineering.app：未找到应用入口 {rel}"]
    text = path.read_text(encoding="utf-8", errors="replace")
    if "def run" not in text:
        return ["engineering.app：应用入口要定义 run(ac)，返回跑完后的页面 id"]
    return []


def _demo_packages(release_package: bool) -> Dict[str, Dict[str, str]]:
    packages = {"test": {"path": TEST_PACKAGE_REL}}
    if release_package:
        packages["release"] = {"path": RELEASE_PACKAGE_REL}
    return packages


def _write_zip(path: Path, app_source: str, variant: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("PACKAGE.txt", variant + "\n")
        archive.writestr("app.py", app_source)


def write_install_packages(root: Path, release: bool = False) -> None:
    """把当前 app.py 打成测试安装包。release 为真时再打正式安装包，并写进清单。"""
    app_path = root / "app.py"
    if not app_path.is_file():
        return
    source = app_path.read_text(encoding="utf-8")
    _write_zip(root / TEST_PACKAGE_REL, source, "test")
    if not release:
        return
    _write_zip(root / RELEASE_PACKAGE_REL, source, "release")
    manifest_path = root / MANIFEST_FILENAME
    if not manifest_path.is_file():
        return
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    engineering = data.get("engineering")
    if not isinstance(engineering, dict):
        return
    packages = engineering.get("packages")
    if not isinstance(packages, dict):
        packages = {}
        engineering["packages"] = packages
    packages.setdefault("test", {"path": TEST_PACKAGE_REL})
    packages["release"] = {"path": RELEASE_PACKAGE_REL}
    manifest_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _package_entry(stage06: Path, variant: str) -> Optional[Path]:
    manifest_path = stage06 / MANIFEST_FILENAME
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    engineering = data.get("engineering") if isinstance(data, dict) else None
    packages = engineering.get("packages") if isinstance(engineering, dict) else None
    item = packages.get(variant) if isinstance(packages, dict) else None
    rel = str(item.get("path") or "").strip() if isinstance(item, dict) else ""
    if not rel:
        return None
    return _confined(stage06, rel)


def release_package_file(stage06: Optional[Path]) -> Optional[Path]:
    if stage06 is None:
        return None
    path = _package_entry(stage06, "release")
    if path is None or not path.is_file():
        return None
    return path


def _package_app_source(path: Path, variant: str) -> Tuple[str, str]:
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            if "app.py" not in names or "PACKAGE.txt" not in names:
                return "", "里要有应用入口"
            kind = archive.read("PACKAGE.txt").decode("utf-8", errors="replace").strip()
            source = archive.read("app.py").decode("utf-8", errors="replace")
    except (OSError, zipfile.BadZipFile):
        return "", "无法打开"
    if kind != variant:
        return "", f"的标记不是 {variant}"
    if "def run" not in source:
        return "", "里的应用入口要定义 run(ac)"
    return source, ""


def engineering_package_reasons(eng: Any, root: Optional[Path]) -> List[str]:
    """有工序 04 的 Then 时，工序 06 先交测试安装包。正式包只在测试包已经测过之后才允许出现。"""
    if not _then_by_ac(root):
        return []
    packages = eng.get("packages") if isinstance(eng, dict) else None
    if not isinstance(packages, dict):
        return ["engineering.packages：缺少测试安装包"]
    reasons: List[str] = []
    test = packages.get("test")
    test_rel = str(test.get("path") or "").strip() if isinstance(test, dict) else ""
    if not test_rel:
        reasons.append("engineering.packages.test：缺少测试安装包")
    elif root is not None:
        path = _confined(root, test_rel)
        if path is None or not path.is_file():
            reasons.append(f"engineering.packages.test：未找到测试安装包 {test_rel}")
        else:
            _source, error = _package_app_source(path, "test")
            if error:
                reasons.append(f"测试安装包{error}")
    if "release" not in packages:
        return reasons
    marker = (root / TEST_PASSED_MARKER) if root is not None else None
    if marker is None or not marker.is_file():
        reasons.append("正式安装包要等测试安装包通过工序 07 的应用测试后再产出")
        return reasons
    release = packages.get("release")
    release_rel = str(release.get("path") or "").strip() if isinstance(release, dict) else ""
    if not release_rel:
        reasons.append("engineering.packages.release：缺少正式安装包")
    elif root is not None:
        path = _confined(root, release_rel)
        if path is None or not path.is_file():
            reasons.append(f"engineering.packages.release：未找到正式安装包 {release_rel}")
        else:
            _source, error = _package_app_source(path, "release")
            if error:
                reasons.append(f"正式安装包{error}")
    return reasons


def _run_entry_scenarios(stage06: Path, app_file: Path) -> List[str]:
    """调用应用入口 run(ac)，核对跑完后的页面出现在该条 Then 里。"""
    clauses = _then_by_ac(stage06)
    if not clauses:
        return []
    path = app_file
    views = set(view_ids_near(stage06))
    reasons: List[str] = []
    for ac, clause in clauses.items():
        try:
            completed = subprocess.run(
                [sys.executable, "-c", _APP_RUNNER, str(path), ac],
                cwd=str(stage06),
                timeout=_TEST_TIMEOUT_SECONDS,
                capture_output=True,
                check=False,
                text=True,
            )
        except subprocess.TimeoutExpired:
            reasons.append(f"{ac} 应用超过 {_TEST_TIMEOUT_SECONDS} 秒未结束")
            continue
        except OSError as exc:
            reasons.append(f"{ac} 应用未能启动: {exc}")
            continue
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip().splitlines()
            tail = detail[-1] if detail else f"退出码 {completed.returncode}"
            reasons.append(f"{ac} 应用未能跑完: {tail}")
            continue
        lines = [line.strip() for line in (completed.stdout or "").splitlines() if line.strip()]
        view = lines[-1] if lines else ""
        if view not in views:
            reasons.append(f"{ac} 应用跑完停在 {view or '(空)'}，不是工序 04 的视图")
        elif view not in clause:
            reasons.append(f"{ac} 应用跑完停在 {view}，验收 Then 里没有这个页面")
    return reasons


def run_packaged_scenarios(stage06: Path, variant: str) -> List[str]:
    """从安装包里取出应用入口再跑验收。测试包做全量核对，正式包做同样的页面核对。"""
    label = "测试安装包" if variant == "test" else "正式安装包"
    path = _package_entry(stage06, variant)
    if path is None or not path.is_file():
        if variant == "release":
            return [RELEASE_PENDING_REASON]
        return [f"工序 06 没有{label}，不能做应用测试"]
    source, error = _package_app_source(path, variant)
    if error:
        return [f"{label}{error}"]
    with tempfile.TemporaryDirectory() as tmp:
        app_file = Path(tmp) / "app.py"
        app_file.write_text(source, encoding="utf-8")
        return _run_entry_scenarios(stage06, app_file)


def run_acceptance_tests(stage06: Path) -> tuple:
    """执行工序 06 清单里的验收测试。返回 (运行记录, 失败原因)。"""
    manifest_path = stage06 / MANIFEST_FILENAME
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return [], ["工序 06 的交付清单无法读取，不能执行验收测试"]
    engineering = data.get("engineering") if isinstance(data, dict) else None
    tests = engineering.get("tests") if isinstance(engineering, dict) else None
    if not isinstance(tests, list) or not tests:
        return [], ["工序 06 没有可执行的验收测试"]
    runs: List[Dict[str, Any]] = []
    reasons: List[str] = []
    clauses = _then_by_ac(stage06)
    for index, item in enumerate(tests):
        if not isinstance(item, dict):
            reasons.append(f"engineering.tests[{index}]：需要 ac、path 和 command")
            continue
        ac = str(item.get("ac") or "").strip()
        rel = str(item.get("path") or "").strip()
        command = item.get("command")
        record: Dict[str, Any] = {"ac": ac, "path": rel, "command": command, "exit_code": None}
        path = _confined(stage06, rel)
        if path is None or not path.is_file():
            reasons.append(f"{ac or '验收'} 的测试文件不存在: {rel or '(空)'}")
            runs.append(record)
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if not _AC_ID.fullmatch(ac) or not _ac_in_text(ac, text):
            reasons.append(f"{ac or '验收'} 的测试文件没有写明该验收编号")
            runs.append(record)
            continue
        clause = clauses.get(ac) or ""
        if clause and clause not in text:
            reasons.append(f"{ac} 的测试文件没有写上工序 04 的 Then：{clause}")
            runs.append(record)
            continue
        command_reasons = _command_reasons(index, command, rel)
        if command_reasons:
            reasons.extend(command_reasons)
            runs.append(record)
            continue
        argv = _resolve_test_command(command, stage06)
        if argv is None:
            reasons.append(f"{ac} 的测试命令无法在工序 06 目录内执行")
            runs.append(record)
            continue
        try:
            completed = subprocess.run(
                argv,
                cwd=str(stage06),
                timeout=_TEST_TIMEOUT_SECONDS,
                capture_output=True,
                check=False,
            )
            record["exit_code"] = completed.returncode
        except subprocess.TimeoutExpired:
            reasons.append(f"{ac} 测试超过 {_TEST_TIMEOUT_SECONDS} 秒未结束")
            runs.append(record)
            continue
        except OSError as exc:
            reasons.append(f"{ac} 测试未能启动: {exc}")
            runs.append(record)
            continue
        runs.append(record)
        if completed.returncode != 0:
            reasons.append(f"{ac} 测试退出码 {completed.returncode}，不能把未关闭的 P0 记为 0")
    return runs, reasons


def _validate_stage07(data: Dict[str, Any], root: Optional[Path] = None) -> List[str]:
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
    if root is None:
        return reasons
    stage06 = sibling_stage_dir(root, "06")
    if stage06 is None:
        reasons.append("没有找到工序 06 的测试清单，不能确认自动化测试结果")
        return reasons
    runs, run_reasons = run_acceptance_tests(stage06)
    qa["runs"] = runs
    reasons.extend(run_reasons)
    if reasons or not _then_by_ac(stage06):
        return reasons
    reasons.extend(run_packaged_scenarios(stage06, "test"))
    if reasons:
        return reasons
    try:
        (stage06 / TEST_PASSED_MARKER).write_text("passed\n", encoding="utf-8")
    except OSError:
        return ["工序 06 的测试安装包结果无法留档"]
    if release_package_file(stage06) is None:
        return [RELEASE_PENDING_REASON]
    return run_packaged_scenarios(stage06, "release")


def _validate_stage08(data: Dict[str, Any]) -> List[str]:
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


def _validate_stage09(data: Dict[str, Any]) -> List[str]:
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


def _validate_stage10(data: Dict[str, Any]) -> List[str]:
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
        reasons.append(f"stage：工序代码 {code} 不在支持的 01~10 范围内")
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
        reasons.extend(_validate_stage01(manifest, root=root, texts=texts))
    elif code == "02":
        reasons.extend(_validate_stage02(manifest))
    elif code == "03":
        reasons.extend(_validate_stage03(manifest))

    elif code == "04":
        reasons.extend(_validate_stage04(manifest, platform))
    elif code == "05":
        reasons.extend(_validate_stage05(manifest, platform, root))
    elif code == "06":
        reasons.extend(_validate_stage06(manifest, client_zero_inference, root))
    elif code == "07":
        reasons.extend(_validate_stage07(manifest, root))
    elif code == "08":
        reasons.extend(_validate_stage08(manifest))
    elif code == "09":
        reasons.extend(_validate_stage09(manifest))
    elif code == "10":
        reasons.extend(_validate_stage10(manifest))

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
