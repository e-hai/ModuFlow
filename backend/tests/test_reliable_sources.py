import json
from pathlib import Path

import pytest

from backend.app.core.config import settings
from backend.app.services.reliable_sources import cite, load_catalog, lookup_reliable_sources


def _catalog_one(source_id, name, host, kind="industry"):
    return [{
        "id": source_id,
        "name": name,
        "kind": kind,
        "hosts": [host],
        "entry_urls": [f"https://{host}/"],
        "enabled": True,
        "search": True,
    }]


def test_fetched_page_stays_observed_and_unfetched_claims_do_not(tmp_path: Path):
    catalog = _catalog_one("yfchuhai", "扬帆出海", "www.yfchuhai.com")

    def search(_query):
        return [
            {"url": "https://www.yfchuhai.com/a", "title": "旅游", "snippet": "摘要而已"},
            {"url": "https://example.com/nope", "title": "外站", "snippet": "外站摘要"},
            {"url": "https://www.yfchuhai.com/empty", "title": "空", "snippet": "只有摘要"},
        ]

    def fetch(url):
        if url == "https://www.yfchuhai.com/a":
            return "<html><title>旅游视频</title><p>公开正文写着视频工具。</p></html>"
        return None

    looked = lookup_reliable_sources(
        "自媒体旅游视频工具", tmp_path, catalog=catalog, search=search, fetch=fetch,
    )
    urls = [row["url"] for row in looked["index"]]
    assert urls == ["https://www.yfchuhai.com/a"]
    assert "外站摘要" not in looked["index"][0]["quote"]
    assert "摘要而已" not in looked["index"][0]["quote"]
    assert "视频工具" in looked["index"][0]["quote"]

    claims = cite([
        {"claim": "公开正文", "status": "已观测", "source": "https://www.yfchuhai.com/a"},
        {"claim": "外站", "status": "已观测", "source": "https://example.com/nope"},
        {"claim": "只有摘要", "status": "已观测", "source": "https://www.yfchuhai.com/empty"},
    ], tmp_path)
    assert [item["status"] for item in claims] == ["已观测", "待验证", "待验证"]


def test_new_catalog_entry_can_be_cited(tmp_path: Path):
    assert not any("example.org" in (item.get("hosts") or []) for item in load_catalog())
    catalog = load_catalog() + _catalog_one("extra", "新增来源", "example.org")

    def search(_query):
        return [{"url": "https://example.org/report", "title": "报告", "snippet": "不采用"}]

    def fetch(url):
        if url == "https://example.org/report":
            return "<html><title>报告</title><p>新增来源的正文。</p></html>"
        return None

    lookup_reliable_sources("视频工具", tmp_path, catalog=catalog, search=search, fetch=fetch)
    claims = cite([
        {"claim": "新增来源的正文", "status": "已观测", "source": "https://example.org/report"},
    ], tmp_path)
    assert claims[0]["status"] == "已观测"


def test_chart_excerpt_keeps_rank_rows_only(tmp_path: Path):
    catalog = [{
        "id": "store_charts",
        "name": "商店榜单",
        "kind": "chart",
        "hosts": ["e-hai.github.io"],
        "entry_urls": ["https://e-hai.github.io/Appstore_Top_30/api/"],
        "enabled": True,
        "search": False,
    }]
    ranking = {
        "date": "2026-11-01",
        "country": "us",
        "chart": "free",
        "store": "app_store",
        "rows": [{
            "curr_rank": 16,
            "name": "CapCut",
            "developer": "Bytedance",
            "price_amount": 0.0,
            "price_currency": "USD",
            "rating": 4.8,
            "rating_count": 10,
        }],
        "market_attribution": {"exec_summary": "广告投放带动排名上升"},
    }

    def fetch(url):
        if url.endswith("dates.json"):
            return json.dumps({"dates": [{"date": "2026-11-01"}]})
        if url.endswith("app_store_us_free_2026-11-01.json"):
            return json.dumps(ranking)
        return None

    looked = lookup_reliable_sources(
        "做一个视频工具", tmp_path, catalog=catalog, search=lambda _query: [], fetch=fetch,
    )
    quotes = "\n".join(row["quote"] for row in looked["index"])
    assert "CapCut" in quotes
    assert "美国（对话未写市场，取美国总榜）" in quotes
    assert "广告投放" not in quotes
    page = tmp_path / looked["index"][0]["path"]
    assert "https://" in page.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_intake_job_uses_excerpts_without_network(monkeypatch, tmp_path):
    from backend.app.services import lead_intake
    from backend.app.services.reliable_sources import intake_workspace

    monkeypatch.setattr(settings, "WORKSPACE_DIR", tmp_path)
    draft_id = "draftjob"
    workspace = intake_workspace(draft_id)
    lead_intake.save_intake_request(workspace, [
        {"role": "user", "content": "做一款视频工具，预算 12,000 美元"},
    ], {})
    result = await lead_intake.run_intake_discuss(
        None, draft_id, use_cli=False, search=lambda _query: [], fetch=lambda _url: None,
    )
    assert result["status"] == "done"
    saved = json.loads((workspace / "result.json").read_text(encoding="utf-8"))
    assert "已记下" in saved["reply"]
    assert "12000" in saved["reply"].replace(",", "") or "12,000" in saved["reply"]
    assert saved["proposal"].get("signals") in (None, [])
    assert (workspace / ".agents" / "mcp_config.json").is_file()
    mounted = (workspace / ".agents" / "mcp_config.json").read_text(encoding="utf-8")
    assert "sources_mcp_server.py" in mounted
    from backend.app.mcp.sources_mcp_server import TOOL
    assert TOOL["name"] == "lookup_reliable_sources"
