"""Stage 04 and 05 handoff manifests. Drafts without one keep the prose checks."""

import json
from pathlib import Path

from backend.app.services.collaboration import check_handoff
from backend.app.services.compliance_engine import audit_stage_compliance
from backend.app.services.deliverable_audit import audit_stage
from backend.app.services.delivery_contract import (
    CONTRACT_STAGES,
    RISK_FLAG_KEYS,
    build_stage_manifest,
    manifest_instruction,
    validate_manifest,
)
from backend.app.services.simulator_deliverables import build_simulated_deliverable

ROOT = Path(__file__).resolve().parents[2]
SM01_PRD = Path(__file__).resolve().parent / "fixtures" / "sm01_stage04_prd.md"


def _flags(**overrides):
    flags = {key: False for key in RISK_FLAG_KEYS}
    flags.update(overrides)
    return flags


def _stage04_manifest(**compliance):
    data = json.loads(build_stage_manifest("04", "交付物_04.md"))
    data["compliance"].update(compliance)
    return data


def test_manifest_path_must_stay_inside_the_stage_directory(tmp_path):
    manifest = _stage04_manifest()
    manifest["artifacts"][0]["path"] = "../authorization.yaml"
    reasons = audit_stage(
        "04",
        [json.dumps(manifest)],
        manifest_root=tmp_path,
    )["reasons"]
    assert any("必须留在本工序目录内" in reason for reason in reasons)


def test_stage04_manifest_passes_with_the_simulator_prd():
    prose, extra = build_simulated_deliverable("04", {"product_name": "清单产品"})
    manifest = json.loads(extra["delivery.manifest.json"])
    result = audit_stage("04", [prose, json.dumps(manifest)], platform="cross_platform")

    assert result["passed"] is True, result["reasons"]
    assert result["contract"] == "delivery.manifest.json"


def test_stage04_manifest_names_missing_att_fallback_and_ad_id_declaration():
    prose, _extra = build_simulated_deliverable("04", {"product_name": "清单产品"})
    att = _stage04_manifest(uses_idfa=True, att_copy="用于衡量广告效果", uses_ad_id=False)
    att_result = audit_stage("04", [prose, json.dumps(att)], platform="cross_platform")
    assert any("compliance.att_denied_fallback" in reason for reason in att_result["reasons"])
    att_compliance = audit_stage_compliance("04", prose, platform="cross_platform", manifest=att)
    assert att_compliance["status"] == "needs_fix"
    assert any("att_denied_fallback" in finding["advice"] for finding in att_compliance["findings"])

    ad_id = _stage04_manifest(
        uses_idfa=False,
        uses_ad_id=True,
        min_audience_age=13,
        ad_id_opt_out_fallback="停用后改为上下文广告",
    )
    ad_result = audit_stage("04", [prose, json.dumps(ad_id)], platform="cross_platform")
    assert any("compliance.ad_id_permission_declared" in reason for reason in ad_result["reasons"])
    ad_compliance = audit_stage_compliance("04", prose, platform="cross_platform", manifest=ad_id)
    assert ad_compliance["status"] == "needs_fix"
    assert any("ad_id_permission_declared" in finding["advice"] for finding in ad_compliance["findings"])


def test_unused_tracking_does_not_create_a_compliance_item():
    prose, _extra = build_simulated_deliverable("04", {"product_name": "清单产品"})
    manifest = _stage04_manifest(uses_idfa=False, uses_ad_id=False)
    result = audit_stage_compliance("04", prose, platform="cross_platform", manifest=manifest)
    assert result["status"] == "passed"
    items = [finding["item"] for finding in result["findings"]]
    assert not any("ATT" in item or "AD_ID" in item for item in items)


def test_old_drafts_without_a_manifest_keep_the_prose_checks():
    prd, _prd_extra = build_simulated_deliverable("04", {"product_name": "旧稿"})
    legacy = audit_stage("04", [prd], platform="cross_platform")
    assert legacy["passed"] is True
    assert "contract" not in legacy

    thin = audit_stage("04", ["只有一段说明，没有视图和验收。"], platform="cross_platform")
    assert thin["passed"] is False


def test_red_flags_come_from_the_manifest_when_it_exists():
    prose = "测试预算：$200\nis_payment_related: true\n"
    quiet = _stage04_manifest()
    quiet["risk_flags"] = _flags(payment=False)
    result = audit_stage("04", [prose, json.dumps(quiet)])
    assert result["red_flags"] == []

    loud = _stage04_manifest()
    loud["risk_flags"] = _flags(payment=True)
    flagged = audit_stage("04", [prose, json.dumps(loud)])
    assert flagged["red_flags"] == ["payment"]


def test_handoff_reads_stage04_manifest_fields_and_keeps_regex_for_old_baselines():
    manifest = _stage04_manifest()
    prose = "这份正文没有视图编号，也没有埋点这两个字。"
    bundled = prose + "\n```json\n" + json.dumps(manifest) + "\n```"
    assert check_handoff("05", {"04": bundled}, ["04", "05"]) == []

    manifest["views"] = []
    empty = prose + "\n```json\n" + json.dumps(manifest) + "\n```"
    missing = check_handoff("05", {"04": empty}, ["04", "05"])
    assert [item["anchor"] for item in missing] == ["视图 id"]

    legacy = "| home | 首页 |\n埋点字典"
    assert check_handoff("05", {"04": legacy}, ["04", "05"]) == []

    no_events = _stage04_manifest()
    no_events.pop("event_dictionary", None)
    views_only = "正文没有埋点这两个字。\n```json\n" + json.dumps(no_events) + "\n```"
    assert check_handoff("05", {"04": views_only}, ["04", "05"]) == []
    assert check_handoff("06", {"04": "验收 AC-01", "05": "design_tokens.json"}, ["04", "05", "06"]) == []


def test_prompt_tells_all_stages_to_keep_the_manifest():
    for i in range(1, 11):
        code = f"{i:02d}"
        inst = manifest_instruction(code, f"交付物_{code}.md")
        assert "delivery.manifest.json" in inst
        assert f'stage 为 "{code}"' in inst
    assert manifest_instruction("00", "交付物_00.md") == ""
    assert manifest_instruction("12", "交付物_12.md") == ""


def test_simulator_builds_valid_manifests_for_all_11_stages():
    for i in range(1, 11):
        if i == 5:
            continue  # 工序 05 的清单指向设计交付包，见 test_design_bundle.py
        code = f"{i:02d}"
        raw = build_stage_manifest(code, f"交付物_{code}.md")
        assert raw, f"Stage {code} should have non-empty manifest"
        manifest = json.loads(raw)
        assert manifest["contract_version"] == "1"
        assert manifest["stage"] == code
        if code != "05":
            reasons = validate_manifest(manifest, platform="cross_platform", client_zero_inference=True)
            assert reasons == [], f"Stage {code} manifest failed validation: {reasons}"


def test_simulated_deliverables_pass_audit_across_all_11_stages(tmp_path):
    for i in range(1, 11):
        code = f"{i:02d}"
        prose, extra = build_simulated_deliverable(code, {"product_name": "全局清单测试", "platform": "cross_platform"})
        assert "delivery.manifest.json" in extra, f"Stage {code} simulated output missing manifest"
        texts = [prose, extra["delivery.manifest.json"]]
        if "index.html" in extra:
            texts.append(extra["index.html"])
        stage_root = None
        if code == "05":
            stage_root = tmp_path / "05_design_implementation"
            for rel, content in extra.items():
                target = stage_root / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
            (stage_root / "交付物_05.md").write_text(prose, encoding="utf-8")
        res = audit_stage(
            code, texts, platform="cross_platform", client_zero_inference=True, manifest_root=stage_root,
        )
        assert res["passed"] is True, f"Stage {code} failed audit: {res['reasons']}"
        assert res["contract"] == "delivery.manifest.json"


def test_stage01_manifest_negative_validation():
    data = json.loads(build_stage_manifest("01", "交付物_01.md"))
    data["market_research"]["target_capture_rate"] = 1.5
    reasons = validate_manifest(data)
    assert any("target_capture_rate" in r for r in reasons)

    data["market_research"]["target_capture_rate"] = 0.05
    data["market_research"]["source"] = ""
    reasons = validate_manifest(data)
    assert any("source" in r for r in reasons)


def test_stage02_manifest_negative_validation_and_pricing_tiers():
    data = json.loads(build_stage_manifest("02", "交付物_02.md"))
    data["unit_economics"]["ltv_cac_ratio"] = 2.1
    reasons = validate_manifest(data)
    assert any("低于 3.0 健康线" in r for r in reasons)

    data["unit_economics"]["ltv_cac_ratio"] = 3.5
    data["unit_economics"]["pricing_tiers"] = []
    reasons = validate_manifest(data)
    assert any("pricing_tiers" in r for r in reasons)


def test_stage03_manifest_negative_validation():
    data = json.loads(build_stage_manifest("03", "交付物_03.md"))
    data["direction"]["uvp"] = ""
    reasons = validate_manifest(data)
    assert any("uvp" in r for r in reasons)

    data["direction"]["uvp"] = "为目标用户提供核心体验"
    data["direction"]["hypotheses"] = [{"id": "H2", "hypothesis": "测试"}]
    reasons = validate_manifest(data)
    assert any("H1" in r for r in reasons)


def test_stage06_checks_test_files_and_token_colors(tmp_path):
    run = tmp_path / "run"
    stage04 = run / "01_product_requirement"
    stage05 = run / "02_design"
    stage06 = run / "03_development"
    stage04.mkdir(parents=True)
    stage05.mkdir()
    stage06.mkdir()
    (stage04 / "delivery.manifest.json").write_text(build_stage_manifest("04", "交付物_04.md"), encoding="utf-8")
    from backend.app.services.design_bundle_sim import build_design_bundle

    for rel, content in build_design_bundle("色值", "ios").items():
        dest = stage05 / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
    (stage05 / "delivery.manifest.json").write_text(build_stage_manifest("05", "交付物_05.md", "ios"), encoding="utf-8")
    (stage06 / "交付物_06.md").write_text("# 开发\n", encoding="utf-8")
    (stage06 / "Theme.kt").write_text('val stray = "#00FFAB"\nfontSize = 13\npadding(7)\n', encoding="utf-8")
    manifest = json.loads(build_stage_manifest("06", "交付物_06.md"))
    reasons = validate_manifest(manifest, root=stage06)
    assert any("未找到测试文件" in item for item in reasons)
    assert any("未找到实现文件" in item for item in reasons)
    assert any("#00ffab" in item for item in reasons)
    assert any("字号 13" in item for item in reasons)
    assert any("间距 7" in item for item in reasons)

    tests = stage06 / "tests"
    tests.mkdir()
    (tests / "test_ac_01.py").write_text('"""AC-01"""\nraise SystemExit(0)\n', encoding="utf-8")
    (tests / "test_ac_02.py").write_text('"""AC-02"""\nraise SystemExit(0)\n', encoding="utf-8")
    for screen in manifest["engineering"]["screens"]:
        dest = stage06 / screen["path"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(f"// {screen['view_id']}\n", encoding="utf-8")
    (stage06 / "Theme.kt").write_text('val primary = "#0E8A5A"\nfontSize = 17\npadding(16)\n', encoding="utf-8")
    missing_then = validate_manifest(manifest, root=stage06)
    assert any("Then" in item and "AC-01" in item for item in missing_then)

    (tests / "test_ac_01.py").write_text('"""AC-01\n10 秒内进入 result 结果页\n"""\nraise SystemExit(0)\n', encoding="utf-8")
    (tests / "test_ac_02.py").write_text('"""AC-02\n作品出现在 history 历史页\n"""\nraise SystemExit(0)\n', encoding="utf-8")
    missing_app = validate_manifest(manifest, root=stage06)
    assert any("应用入口" in item for item in missing_app)
    from backend.app.services.delivery_contract import DEMO_APP, RELEASE_PACKAGE_REL, write_install_packages

    (stage06 / "app.py").write_text(DEMO_APP, encoding="utf-8")
    missing_package = validate_manifest(manifest, root=stage06)
    assert any("测试安装包" in item for item in missing_package)
    write_install_packages(stage06, release=False)
    assert validate_manifest(manifest, root=stage06) == []
    manifest["engineering"]["packages"]["release"] = {"path": RELEASE_PACKAGE_REL}
    write_install_packages(stage06, release=True)
    early_release = validate_manifest(manifest, root=stage06)
    assert any("后再产出" in item for item in early_release)
    del manifest["engineering"]["packages"]["release"]
    assert validate_manifest(manifest, root=stage06) == []


def test_stage06_manifest_negative_validation():
    data = json.loads(build_stage_manifest("06", "交付物_06.md"))
    data["engineering"]["coverage_percent"] = 72.0
    reasons = validate_manifest(data)
    assert any("coverage_percent" in r for r in reasons)

    data["engineering"]["coverage_percent"] = 85.0
    data["engineering"]["zero_client_inference"] = False
    reasons = validate_manifest(data, client_zero_inference=True)
    assert any("zero_client_inference" in r for r in reasons)


def _stage07_workspace(tmp_path: Path, script: str) -> Path:
    run = tmp_path / "run"
    stage06 = run / "03_development"
    stage07 = run / "04_testing"
    stage06.mkdir(parents=True)
    stage07.mkdir()
    (stage06 / "tests").mkdir()
    (stage06 / "tests" / "test_ac_01.py").write_text(script, encoding="utf-8")
    (stage06 / "delivery.manifest.json").write_text(
        build_stage_manifest("06", "交付物_06.md"),
        encoding="utf-8",
    )
    (stage07 / "交付物_07.md").write_text("# 测试\n", encoding="utf-8")
    return stage07


def test_stage07_runs_stage06_tests_and_rejects_a_nonzero_exit(tmp_path):
    stage07 = _stage07_workspace(tmp_path, '"""AC-01"""\nraise SystemExit(1)\n')
    manifest = json.loads(build_stage_manifest("07", "交付物_07.md"))
    reasons = validate_manifest(manifest, root=stage07)
    assert any("退出码 1" in item and "AC-01" in item for item in reasons)

    passing = stage07.parent / "03_development" / "tests" / "test_ac_01.py"
    passing.write_text('"""AC-01"""\nraise SystemExit(0)\n', encoding="utf-8")
    (stage07.parent / "03_development" / "tests" / "test_ac_02.py").write_text(
        '"""AC-02"""\nraise SystemExit(0)\n',
        encoding="utf-8",
    )
    assert validate_manifest(manifest, root=stage07) == []

    (stage07.parent / "03_development" / "tests" / "test_ac_02.py").write_text(
        "raise SystemExit(0)\n",
        encoding="utf-8",
    )
    blank = validate_manifest(manifest, root=stage07)
    assert any("没有写明" in item and "AC-02" in item for item in blank)

    stage04 = stage07.parent / "01_product_requirement"
    stage04.mkdir()
    (stage04 / "delivery.manifest.json").write_text(build_stage_manifest("04", "交付物_04.md"), encoding="utf-8")
    (stage07.parent / "03_development" / "tests" / "test_ac_01.py").write_text(
        '"""AC-01"""\nraise SystemExit(0)\n', encoding="utf-8",
    )
    (stage07.parent / "03_development" / "tests" / "test_ac_02.py").write_text(
        '"""AC-02"""\nraise SystemExit(0)\n', encoding="utf-8",
    )
    missing_then = validate_manifest(manifest, root=stage07)
    assert any("Then" in item and "AC-01" in item for item in missing_then)
    (stage07.parent / "03_development" / "tests" / "test_ac_01.py").write_text(
        '"""AC-01\n10 秒内进入 result 结果页\n"""\nraise SystemExit(0)\n', encoding="utf-8",
    )
    (stage07.parent / "03_development" / "tests" / "test_ac_02.py").write_text(
        '"""AC-02\n作品出现在 history 历史页\n"""\nraise SystemExit(0)\n', encoding="utf-8",
    )
    missing_package = validate_manifest(manifest, root=stage07)
    assert any("测试安装包" in item for item in missing_package)
    stage06 = stage07.parent / "03_development"
    from backend.app.services.delivery_contract import DEMO_APP, write_install_packages

    (stage06 / "app.py").write_text('def run(ac):\n    return "home"\n', encoding="utf-8")
    write_install_packages(stage06, release=False)
    wrong_view = validate_manifest(manifest, root=stage07)
    assert any("停在 home" in item and "AC-01" in item for item in wrong_view)
    (stage06 / "app.py").write_text(DEMO_APP, encoding="utf-8")
    write_install_packages(stage06, release=False)
    pending_release = validate_manifest(manifest, root=stage07)
    assert any("正式安装包尚未产出" in item for item in pending_release)
    write_install_packages(stage06, release=True)
    assert validate_manifest(manifest, root=stage07) == []


def test_stage07_manifest_negative_validation():
    data = json.loads(build_stage_manifest("07", "交付物_07.md"))
    data["quality"]["open_p0"] = 1
    reasons = validate_manifest(data)
    assert any("open_p0" in r for r in reasons)


def test_stage08_manifest_negative_validation():
    data = json.loads(build_stage_manifest("08", "交付物_08.md"))
    data["release"]["has_remote_killswitch"] = False
    reasons = validate_manifest(data)
    assert any("has_remote_killswitch" in r for r in reasons)


def test_stage09_manifest_negative_validation():
    data = json.loads(build_stage_manifest("09", "交付物_09.md"))
    data["acquisition"]["ecac_usd"] = 5.0
    data["acquisition"]["ecac_limit_usd"] = 2.5
    reasons = validate_manifest(data)
    assert any("超过熔断线" in r for r in reasons)


def test_stage10_manifest_negative_validation():
    data = json.loads(build_stage_manifest("10", "交付物_10.md"))
    data["retention"]["backlog_items"] = []
    reasons = validate_manifest(data)
    assert any("backlog_items" in r for r in reasons)


def test_simulator_writes_the_same_manifest_shape():
    _prose, extra = build_simulated_deliverable("04", {"product_name": "演示"})
    manifest = json.loads(extra["delivery.manifest.json"])
    assert manifest["stage"] == "04"
    assert manifest["views"][0] == {"id": "home", "name": "首页"}
    assert len({item["id"] for item in manifest["views"]}) == len(manifest["views"])

    _prd, prd_extra = build_simulated_deliverable("04", {"product_name": "演示"})
    prd_manifest = json.loads(prd_extra["delivery.manifest.json"])
    assert prd_manifest["views"][0] == {"id": "home", "name": "首页"}
    first = prd_manifest["acceptance_criteria"][0]
    assert first["id"] == "AC-01" and first["view_id"] == "home" and first["then"]
    assert prd_manifest["compliance"]["uses_idfa"] is False
    assert prd_manifest["compliance"]["uses_ad_id"] is False


def test_sm01_stage04_prose_passes_compliance_with_a_manifest():
    prose = SM01_PRD.read_text(encoding="utf-8")
    manifest = _stage04_manifest(
        uses_idfa=True,
        att_copy="StillMinute 使用此标识符衡量广告效果。",
        att_denied_fallback="拒绝后只保留本应用内行为统计，不做跨应用追踪。",
        uses_ad_id=True,
        ad_id_permission_declared=True,
        min_audience_age=13,
        ad_id_opt_out_fallback="停用广告标识符后改为上下文广告，不中断核心功能。",
    )
    result = audit_stage_compliance("04", prose, platform="cross_platform", manifest=manifest)

    assert result["status"] == "passed", [
        finding["advice"] for finding in result["findings"] if not finding["passed"]
    ]
    checked = {finding["item"] for finding in result["findings"]}
    assert "Apple App Tracking Transparency (ATT) 弹窗规格" in checked
    assert "Google Play Advertising ID (AD_ID) 权限声明与家庭政策" in checked
    assert all(finding["passed"] for finding in result["findings"])
