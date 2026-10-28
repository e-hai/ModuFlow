"""Deliverable checkers read workspace files and do not honor hardcoded passes."""

import json
import subprocess
import sys
from pathlib import Path

from backend.app.mcp.role_mcp_server import execute_role_tool
from backend.app.services.deliverable_audit import audit_unit_economics, lint_markdown

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
