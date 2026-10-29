"""Stage 04 and 05 handoff manifests. Drafts without one keep the prose checks."""

import json
from pathlib import Path
from types import SimpleNamespace

from backend.app.core.config import settings
from backend.app.services.collaboration import check_handoff
from backend.app.services.compliance_engine import audit_stage_compliance
from backend.app.services.deliverable_audit import artifact_audit_texts, audit_stage
from backend.app.services.delivery_contract import (
    CONTRACT_STAGES,
    RISK_FLAG_KEYS,
    build_stage_manifest,
    manifest_instruction,
    validate_manifest,
)
from backend.app.services.simulator_deliverables import build_simulated_deliverable

ROOT = Path(__file__).resolve().parents[2]
SM01_PRD = (
    ROOT
    / "data/workspaces/init-stillminute-20261028/products/SM01/v1.0.0"
    / "05_05_产品需求定义/交付物_05_产品需求定义.md"
)


def _flags(**overrides):
    flags = {key: False for key in RISK_FLAG_KEYS}
    flags.update(overrides)
    return flags


def _html() -> str:
    return (
        "<!DOCTYPE html><html><body><button id='cta'>预约</button>"
        "<script>document.getElementById('cta').addEventListener('click', function () {});</script>"
        + ("<!-- pad -->" * 80)
        + "</html>"
    )


def _stage04_manifest(**fakedoor):
    data = json.loads(build_stage_manifest("04", "交付物_04.md"))
    data["fakedoor"].update(fakedoor)
    return data


def _stage05_manifest(**compliance):
    data = json.loads(build_stage_manifest("05", "交付物_05.md"))
    data["compliance"].update(compliance)
    return data


def test_stage04_manifest_passes_when_the_page_is_interactive():
    prose = "测试预算：$200\n外测尚未执行，指标待回填。\n"
    manifest = _stage04_manifest()
    result = audit_stage("04", [prose, _html(), json.dumps(manifest)])

    assert result["passed"] is True
    assert result["contract"] == "delivery.manifest.json"
    assert result["red_flags"] == []


def test_stage04_manifest_names_a_missing_page_and_rejects_invented_results():
    prose = "测试预算：$200\n"
    missing = audit_stage("04", [prose, json.dumps(_stage04_manifest())])
    assert missing["passed"] is False
    assert any(reason.startswith("fakedoor.entry：未找到") for reason in missing["reasons"])

    invented = _stage04_manifest(measured_results={"ctr": 0.12})
    result = audit_stage("04", [prose, _html(), json.dumps(invented)])
    assert any("fakedoor.measured_results" in reason for reason in result["reasons"])


def test_stage04_manifest_on_disk_requires_the_referenced_file(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "WORKSPACE_DIR", tmp_path)
    stage = tmp_path / "04"
    stage.mkdir()
    report = "测试预算：$200\n"
    (stage / "交付物_04.md").write_text(report, encoding="utf-8")
    (stage / "delivery.manifest.json").write_text(
        json.dumps(_stage04_manifest()), encoding="utf-8",
    )
    artifact = SimpleNamespace(content=report, storage_rel_path="04", entry_file="index.html")

    blocked = audit_stage("04", artifact_audit_texts([artifact]), manifest_root=stage)
    assert blocked["passed"] is False
    assert any("fakedoor.entry" in reason for reason in blocked["reasons"])

    (stage / "index.html").write_text(_html(), encoding="utf-8")
    passed = audit_stage("04", artifact_audit_texts([artifact]), manifest_root=stage)
    assert passed["passed"] is True


def test_manifest_path_must_stay_inside_the_stage_directory(tmp_path):
    manifest = _stage04_manifest()
    manifest["artifacts"][0]["path"] = "../authorization.yaml"
    reasons = audit_stage(
        "04",
        ["测试预算：$200\n", _html(), json.dumps(manifest)],
        manifest_root=tmp_path,
    )["reasons"]
    assert any("必须留在本工序目录内" in reason for reason in reasons)


def test_stage05_manifest_passes_with_the_simulator_prd():
    prose, extra = build_simulated_deliverable("05", {"product_name": "清单产品"})
    manifest = json.loads(extra["delivery.manifest.json"])
    result = audit_stage("05", [prose, json.dumps(manifest)], platform="cross_platform")

    assert result["passed"] is True, result["reasons"]
    assert result["contract"] == "delivery.manifest.json"


def test_stage05_manifest_names_missing_att_fallback_and_ad_id_declaration():
    prose, _extra = build_simulated_deliverable("05", {"product_name": "清单产品"})
    att = _stage05_manifest(uses_idfa=True, att_copy="用于衡量广告效果", uses_ad_id=False)
    att_result = audit_stage("05", [prose, json.dumps(att)], platform="cross_platform")
    assert any("compliance.att_denied_fallback" in reason for reason in att_result["reasons"])
    att_compliance = audit_stage_compliance("05", prose, platform="cross_platform", manifest=att)
    assert att_compliance["status"] == "needs_fix"
    assert any("att_denied_fallback" in finding["advice"] for finding in att_compliance["findings"])

    ad_id = _stage05_manifest(
        uses_idfa=False,
        uses_ad_id=True,
        min_audience_age=13,
        ad_id_opt_out_fallback="停用后改为上下文广告",
    )
    ad_result = audit_stage("05", [prose, json.dumps(ad_id)], platform="cross_platform")
    assert any("compliance.ad_id_permission_declared" in reason for reason in ad_result["reasons"])
    ad_compliance = audit_stage_compliance("05", prose, platform="cross_platform", manifest=ad_id)
    assert ad_compliance["status"] == "needs_fix"
    assert any("ad_id_permission_declared" in finding["advice"] for finding in ad_compliance["findings"])


def test_unused_tracking_does_not_create_a_compliance_item():
    prose, _extra = build_simulated_deliverable("05", {"product_name": "清单产品"})
    manifest = _stage05_manifest(uses_idfa=False, uses_ad_id=False)
    result = audit_stage_compliance("05", prose, platform="cross_platform", manifest=manifest)
    assert result["status"] == "passed"
    items = [finding["item"] for finding in result["findings"]]
    assert not any("ATT" in item or "AD_ID" in item for item in items)


def test_old_drafts_without_a_manifest_keep_the_prose_checks():
    fakedoor, _extra = build_simulated_deliverable("04", {"product_name": "旧稿"})
    passed = audit_stage("04", [fakedoor])
    assert passed["passed"] is True
    assert "contract" not in passed

    thin = audit_stage("04", ["测试预算：$200\n只有说明，没有页面。"])
    assert thin["passed"] is False
    assert any("未找到可交互 H5" in reason for reason in thin["reasons"])

    prd, _prd_extra = build_simulated_deliverable("05", {"product_name": "旧稿"})
    legacy = audit_stage("05", [prd], platform="cross_platform")
    assert legacy["passed"] is True
    assert "contract" not in legacy


def test_red_flags_come_from_the_manifest_when_it_exists():
    prose = "测试预算：$200\nis_payment_related: true\n"
    quiet = _stage04_manifest()
    quiet["risk_flags"] = _flags(payment=False)
    result = audit_stage("04", [prose, _html(), json.dumps(quiet)])
    assert result["red_flags"] == []

    loud = _stage04_manifest()
    loud["risk_flags"] = _flags(payment=True)
    flagged = audit_stage("04", [prose, _html(), json.dumps(loud)])
    assert flagged["red_flags"] == ["payment"]


def test_handoff_reads_stage05_manifest_fields_and_keeps_regex_for_old_baselines():
    manifest = _stage05_manifest()
    prose = "这份正文没有视图编号，也没有埋点这两个字。"
    bundled = prose + "\n```json\n" + json.dumps(manifest) + "\n```"
    assert check_handoff("06", {"05": bundled}, ["05", "06"]) == []

    manifest["views"] = []
    empty = prose + "\n```json\n" + json.dumps(manifest) + "\n```"
    missing = check_handoff("06", {"05": empty}, ["05", "06"])
    assert [item["anchor"] for item in missing] == ["视图索引 V-xx"]

    legacy = "视图 V-01\n埋点字典"
    assert check_handoff("06", {"05": legacy}, ["05", "06"]) == []
    assert check_handoff("07", {"05": "验收 AC-01", "06": "design_tokens.json"}, ["05", "06", "07"]) == []


def test_prompt_tells_all_stages_to_keep_the_manifest():
    for i in range(1, 12):
        code = f"{i:02d}"
        inst = manifest_instruction(code, f"交付物_{code}.md")
        assert "delivery.manifest.json" in inst
        assert f'stage 为 "{code}"' in inst
    assert manifest_instruction("00", "交付物_00.md") == ""
    assert manifest_instruction("12", "交付物_12.md") == ""


def test_simulator_builds_valid_manifests_for_all_11_stages():
    for i in range(1, 12):
        code = f"{i:02d}"
        raw = build_stage_manifest(code, f"交付物_{code}.md")
        assert raw, f"Stage {code} should have non-empty manifest"
        manifest = json.loads(raw)
        assert manifest["contract_version"] == "1"
        assert manifest["stage"] == code
        # Stage 04 references index.html which is tested separately with HTML content
        if code != "04":
            reasons = validate_manifest(manifest, platform="cross_platform", client_zero_inference=True)
            assert reasons == [], f"Stage {code} manifest failed validation: {reasons}"


def test_simulated_deliverables_pass_audit_across_all_11_stages():
    for i in range(1, 12):
        code = f"{i:02d}"
        prose, extra = build_simulated_deliverable(code, {"product_name": "全局清单测试", "platform": "cross_platform"})
        assert "delivery.manifest.json" in extra, f"Stage {code} simulated output missing manifest"
        texts = [prose, extra["delivery.manifest.json"]]
        if "index.html" in extra:
            texts.append(extra["index.html"])
        res = audit_stage(code, texts, platform="cross_platform", client_zero_inference=True)
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


def test_stage06_manifest_negative_validation():
    data = json.loads(build_stage_manifest("06", "交付物_06.md"))
    data["design"]["safe_area"]["top_safe_padding_pt"] = 50
    reasons = validate_manifest(data, platform="ios")
    assert any("top_safe_padding_pt" in r for r in reasons)


def test_stage07_manifest_negative_validation():
    data = json.loads(build_stage_manifest("07", "交付物_07.md"))
    data["engineering"]["coverage_percent"] = 72.0
    reasons = validate_manifest(data)
    assert any("coverage_percent" in r for r in reasons)

    data["engineering"]["coverage_percent"] = 85.0
    data["engineering"]["zero_client_inference"] = False
    reasons = validate_manifest(data, client_zero_inference=True)
    assert any("zero_client_inference" in r for r in reasons)


def test_stage08_manifest_negative_validation():
    data = json.loads(build_stage_manifest("08", "交付物_08.md"))
    data["quality"]["open_p0"] = 1
    reasons = validate_manifest(data)
    assert any("open_p0" in r for r in reasons)


def test_stage09_manifest_negative_validation():
    data = json.loads(build_stage_manifest("09", "交付物_09.md"))
    data["release"]["has_remote_killswitch"] = False
    reasons = validate_manifest(data)
    assert any("has_remote_killswitch" in r for r in reasons)


def test_stage10_manifest_negative_validation():
    data = json.loads(build_stage_manifest("10", "交付物_10.md"))
    data["acquisition"]["ecac_usd"] = 5.0
    data["acquisition"]["ecac_limit_usd"] = 2.5
    reasons = validate_manifest(data)
    assert any("超过熔断线" in r for r in reasons)


def test_stage11_manifest_negative_validation():
    data = json.loads(build_stage_manifest("11", "交付物_11.md"))
    data["retention"]["backlog_items"] = []
    reasons = validate_manifest(data)
    assert any("backlog_items" in r for r in reasons)


def test_simulator_writes_the_same_manifest_shape():
    _prose, extra = build_simulated_deliverable("04", {"product_name": "演示"})
    manifest = json.loads(extra["delivery.manifest.json"])
    assert manifest["stage"] == "04"
    assert manifest["fakedoor"]["entry"] == "index.html"
    assert manifest["fakedoor"]["interactive"] is True
    assert manifest["fakedoor"]["measured_results"] == "pending"
    assert "index.html" in extra

    _prd, prd_extra = build_simulated_deliverable("05", {"product_name": "演示"})
    prd_manifest = json.loads(prd_extra["delivery.manifest.json"])
    assert prd_manifest["views"][0] == "V-01"
    assert prd_manifest["acceptance_criteria"][0] == "AC-01"
    assert prd_manifest["compliance"]["uses_idfa"] is False
    assert prd_manifest["compliance"]["uses_ad_id"] is False


def test_sm01_stage05_prose_passes_compliance_with_a_manifest():
    prose = SM01_PRD.read_text(encoding="utf-8")
    manifest = _stage05_manifest(
        uses_idfa=True,
        att_copy="StillMinute 使用此标识符衡量广告效果。",
        att_denied_fallback="拒绝后只保留本应用内行为统计，不做跨应用追踪。",
        uses_ad_id=True,
        ad_id_permission_declared=True,
        min_audience_age=13,
        ad_id_opt_out_fallback="停用广告标识符后改为上下文广告，不中断核心功能。",
    )
    result = audit_stage_compliance("05", prose, platform="cross_platform", manifest=manifest)

    assert result["status"] == "passed", [
        finding["advice"] for finding in result["findings"] if not finding["passed"]
    ]
    checked = {finding["item"] for finding in result["findings"]}
    assert "Apple App Tracking Transparency (ATT) 弹窗规格" in checked
    assert "Google Play Advertising ID (AD_ID) 权限声明与家庭政策" in checked
    assert all(finding["passed"] for finding in result["findings"])
