"""工序 01 的三个输入必须对上摘录，确认单直接列出这些数。"""

import json

from backend.app.services.deliverable_audit import audit_stage
from backend.app.services.delivery_contract import RISK_FLAG_KEYS
from backend.app.services.gate_copy import describe_passed_stage
from backend.app.services.lead_service import compose_lead_rationale
from backend.app.services.reliable_sources import mount_lookup_tool, prepare_stage_sources
from backend.app.services.skill_mcp_mounter import mount_role_skills_and_mcp

_URL = "https://www.yfchuhai.com/a"
_QUOTE = "公开正文写着月搜索量 12000，客单价 4.5 美元。"


def _sources(root, quote=_QUOTE):
    sources = root / "sources"
    sources.mkdir(parents=True)
    (sources / "s1.md").write_text(f"URL: {_URL}\n\n{quote}\n", encoding="utf-8")
    (sources / "index.json").write_text(json.dumps([{
        "url": _URL,
        "path": "sources/s1.md",
        "source_name": "扬帆出海",
        "quote": quote,
    }], ensure_ascii=False), encoding="utf-8")


def _manifest(volume=12000, rate=0.05, arpu=4.5, *, rate_basis="assumption"):
    annual = int(volume * 12 * rate)
    som = round(annual * arpu, 2)
    return {
        "contract_version": "1",
        "stage": "01",
        "artifacts": [{"role": "report", "path": "交付物_01.md"}],
        "risk_flags": {key: False for key in RISK_FLAG_KEYS},
        "market_research": {
            "market": "美国",
            "demand_definition": "视频工具",
            "monthly_search_volume": volume,
            "target_capture_rate": rate,
            "blended_arpu_usd": arpu,
            "annual_target_installs": annual,
            "first_year_som_usd": som,
            "citations": {
                "monthly_search_volume": {"basis": "excerpt", "url": _URL},
                "target_capture_rate": {"basis": rate_basis},
                "blended_arpu_usd": {"basis": "excerpt", "url": _URL},
            },
            "source": "扬帆出海",
            "verdict": "GO",
        },
    }


def test_numbers_in_the_excerpt_pass_and_the_sheet_lists_them(tmp_path):
    _sources(tmp_path)
    prose = "首年盘子 $32,400\n"
    (tmp_path / "交付物_01.md").write_text(prose, encoding="utf-8")
    result = audit_stage("01", [prose, json.dumps(_manifest(), ensure_ascii=False)], manifest_root=tmp_path)
    assert result["passed"], result["reasons"]
    assert result["annual_target_installs"] == 7200
    assert result["first_year_som_usd"] == 32400.0
    assert result["capture_rate_basis"] == "assumption"
    sheet = describe_passed_stage("01", "市场研究", result)
    assert "1.2 万" in sheet["recommendation"]
    assert "5%" in sheet["recommendation"]
    assert "4.50 美元" in sheet["recommendation"]
    assert "假设" in sheet["recommendation"]
    assert "扬帆出海" in sheet["evidence"]
    code, text = compose_lead_rationale(
        escalated=False,
        escalation_reasons=[],
        blocking_findings=[],
        note="取得比例是假设。",
    )
    assert code == "approved"
    assert "取得比例是假设" in text
    assert "建议放行" in text


def test_volume_missing_from_the_excerpt_fails(tmp_path):
    _sources(tmp_path)
    result = audit_stage("01", [json.dumps(_manifest(volume=99999), ensure_ascii=False)], manifest_root=tmp_path)
    assert result["passed"] is False
    assert any("月搜索量" in reason for reason in result["reasons"])


def test_prose_som_that_disagrees_with_the_product_fails(tmp_path):
    _sources(tmp_path)
    prose = "首年盘子 $9,999\n"
    result = audit_stage("01", [prose, json.dumps(_manifest(), ensure_ascii=False)], manifest_root=tmp_path)
    assert result["passed"] is False
    assert any("9,999" in reason for reason in result["reasons"])


def test_demo_draft_skips_the_excerpt_check(tmp_path):
    _sources(tmp_path, quote="这篇没有要填的数字。")
    prose = "离线模拟器生成的演示稿。\n"
    (tmp_path / "交付物_01.md").write_text(prose, encoding="utf-8")
    result = audit_stage(
        "01",
        [prose, json.dumps(_manifest(volume=99999), ensure_ascii=False)],
        manifest_root=tmp_path,
    )
    assert result["passed"], result["reasons"]


def test_lookup_mount_keeps_the_existing_mr_server(tmp_path):
    mount_role_skills_and_mcp(tmp_path, primary_role_code="mr", collaborator_role_codes=["ba"])
    mount_lookup_tool(tmp_path)
    servers = json.loads((tmp_path / ".agents" / "mcp_config.json").read_text(encoding="utf-8"))["mcpServers"]
    assert "moduflow-mr-mcp" in servers
    assert "moduflow-sources" in servers
    assert "sources_mcp_server.py" in " ".join(servers["moduflow-sources"]["args"])


def test_prepare_writes_excerpts_from_the_fake_fetch(tmp_path):
    def fetch(url):
        return "<html><title>报告</title>公开正文写着视频工具</html>"

    prepare_stage_sources(tmp_path, "美国 视频工具", search=lambda _query: [], fetch=fetch)
    index = json.loads((tmp_path / "sources" / "index.json").read_text(encoding="utf-8"))
    assert index
    assert "视频工具" in index[0]["quote"]
    assert "moduflow-sources" in json.loads((tmp_path / ".agents" / "mcp_config.json").read_text(encoding="utf-8"))["mcpServers"]
