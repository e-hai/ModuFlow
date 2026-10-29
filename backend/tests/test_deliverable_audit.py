"""Deliverable checkers read workspace files and do not honor hardcoded passes."""

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from backend.app.mcp.role_mcp_server import execute_role_tool

from backend.app.core.config import settings
from backend.app.services.deliverable_audit import (
    artifact_audit_texts,
    audit_fakedoor,
    audit_som,
    audit_unit_economics,
    handoff_som_text,
    lint_markdown,
)
from backend.app.services.collaboration import check_handoff

ROOT = Path(__file__).resolve().parents[2]
UE_SCRIPT = ROOT / "backend" / "skills" / "ba" / "ba-unit-economics-calculator" / "scripts" / "ue_sim.py"


def test_unit_economics_script_fails_without_workspace_file(tmp_path):
    proc = subprocess.run(
        [sys.executable, str(UE_SCRIPT)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    payload = json.loads(proc.stdout)
    assert proc.returncode != 0
    assert payload["passed"] is False


def test_unit_economics_script_reads_workspace_json(tmp_path):
    (tmp_path / "unit_economics.json").write_text(json.dumps({
        "organic_share": 0.2,
        "paid_cpi_usd": 1.0,
        "ad_arpu_usd": 2.0,
        "iap_conversion_rate": 0.1,
        "iap_net_arppu_usd": 20,
    }), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(UE_SCRIPT)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    payload = json.loads(proc.stdout)
    assert proc.returncode == 0, proc.stderr
    assert payload["passed"] is True
    assert payload["ltv_cac_ratio"] >= 3


def test_mcp_pricing_claim_cannot_pass_without_files(tmp_path):
    result = execute_role_tool("ba", tmp_path, "simulate_unit_economics", {
        "organic_share": 0.2,
        "paid_cpi_usd": 1.0,
        "ad_arpu_usd": 2.0,
        "iap_conversion_rate": 0.1,
        "iap_net_arppu_usd": 20,
    })
    assert result["passed"] is False
    assert result.get("claimed")


def test_mcp_hig_defaults_do_not_pass(tmp_path):
    result = execute_role_tool("ux", tmp_path, "audit_hig_safe_area", {
        "top_safe_padding_pt": 74,
        "min_touch_target_pt": 44,
    })
    assert result["passed"] is False


def test_prd_below_100_does_not_pass():
    result = lint_markdown("## 负责人 30 秒拍板摘要卡\n只有摘要")
    assert result["score"] < 100
    assert result["passed"] is False
    assert result["status"] != "ok"


def test_ratio_below_three_fails():
    text = json.dumps({
        "organic_share": 0.0,
        "paid_cpi_usd": 2.0,
        "ad_arpu_usd": 0.5,
        "iap_conversion_rate": 0.01,
        "iap_net_arppu_usd": 10,
    })
    result = audit_unit_economics([text])
    assert result["passed"] is False
    assert result["ltv_cac_ratio"] < 3


def test_fakedoor_check_reads_the_workspace_index_html(tmp_path, monkeypatch):
    stage = tmp_path / "04"
    stage.mkdir()
    (stage / "index.html").write_text(
        "<!DOCTYPE html><html><body><button id='cta'>预约</button>"
        "<script>document.getElementById('cta').addEventListener('click', function () {});</script>"
        + ("<!-- pad -->" * 40)
        + "</html>",
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "WORKSPACE_DIR", tmp_path)
    report = "# 低成本市场验证\n测试预算：$200\n"
    artifact = SimpleNamespace(content=report, storage_rel_path="04", entry_file="index.html")

    assert audit_fakedoor([report])["passed"] is False
    assert audit_fakedoor(artifact_audit_texts([artifact]))["passed"] is True
    outside = SimpleNamespace(content=report, storage_rel_path="../secret", entry_file="index.html")
    assert artifact_audit_texts([outside]) == [report]


_FIELDS = (
    "monthly_search_volume: 350000\n"
    "target_capture_rate: 0.008\n"
    "blended_arpu_usd: 66.86\n"
    "source: 测试夹具：假设/待验证\n"
)


def test_stage01_prose_som_must_match_the_computed_figure():
    agreed = _FIELDS + "首年盘子约 224.6 万美元\n"
    agreed_audit = audit_som([agreed])
    assert agreed_audit["passed"] is True
    assert agreed_audit["first_year_som_usd"] == 2246496.0

    conflict = _FIELDS + "首年现实有效营收盘子（SOM）为 **$187,200 USD**\n移交首年 SOM $18.72 万\n"
    conflict_audit = audit_som([conflict])
    assert conflict_audit["passed"] is False
    assert conflict_audit["first_year_som_usd"] == 2246496.0
    assert "187,200" in conflict_audit["reasons"][0]
    assert "2,246,496.00" in conflict_audit["reasons"][0]

    handed = handoff_som_text(conflict)
    assert "187,200" not in handed
    assert "18.72" not in handed
    assert "2,246,496.00" in handed
    assert check_handoff("02", {"01": conflict}, ["01", "02"]) == []
    assert check_handoff("02", {"01": "首年盘子 $187,200"}, ["01"]) != []
