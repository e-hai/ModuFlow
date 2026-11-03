"""可靠来源。

目录全局一份。每次查阅把摘录写进调用方工作区的 sources/。
对外两个方法：lookup_reliable_sources 给 harness 调用，cite 给平台在草案写完后调用。
"""

from __future__ import annotations

import json
import os
import re
import sys
from html import unescape
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

import yaml

from backend.app.core.config import settings

CATALOG_PATH = Path(__file__).with_name("reliable_sources.yaml")
OBSERVED = "已观测"
UNVERIFIED = "待验证"
MAX_PAGES = 12
MAX_BYTES = 200_000
FETCH_TIMEOUT = 15
CHART_ROWS = 5

Fetch = Callable[[str], Optional[str]]
Search = Callable[[str], List[Dict[str, str]]]

_MARKETS = (
    ("美国", "us", "美国"),
    ("北美", "us", "美国"),
    ("日本", "jp", "日本"),
    ("韩国", "kr", "韩国"),
    ("英国", "gb", "英国"),
    ("德国", "de", "德国"),
    ("法国", "fr", "法国"),
    ("加拿大", "ca", "加拿大"),
    ("澳大利亚", "au", "澳大利亚"),
    ("印度", "in", "印度"),
    ("巴西", "br", "巴西"),
    ("台湾", "tw", "台湾"),
    ("香港", "hk", "香港"),
)
_URL_RE = re.compile(r"https://[^\s<>'\"）)]+")
_TAG_RE = re.compile(r"<[^>]+>")
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
_SPACE_RE = re.compile(r"\s+")


def load_catalog(path: Optional[Path] = None) -> List[Dict[str, Any]]:
    raw = yaml.safe_load((path or CATALOG_PATH).read_text(encoding="utf-8")) or {}
    rows = []
    for item in raw.get("sources") or []:
        if not isinstance(item, dict) or not item.get("enabled", True):
            continue
        rows.append(item)
    return rows


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def _match_source(url: str, catalog: Iterable[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    host = _host(url)
    best = None
    best_len = -1
    for source in catalog:
        for allowed in source.get("hosts") or []:
            allowed = str(allowed).lower()
            if host == allowed or host.endswith("." + allowed):
                if len(allowed) > best_len:
                    best = source
                    best_len = len(allowed)
    return best


def _country(question: str) -> tuple[str, str, bool]:
    for label, code, display in _MARKETS:
        if label in (question or ""):
            return code, display, True
    return "us", "美国", False


def _query_text(question: str) -> str:
    text = _URL_RE.sub(" ", question or "")
    text = _SPACE_RE.sub(" ", text).strip()
    return text[:80] or "app"


def default_fetch(url: str) -> Optional[str]:
    if not url.startswith("https://"):
        return None
    request = Request(url, headers={"User-Agent": "ModuFlow reliable-sources"})
    try:
        with urlopen(request, timeout=FETCH_TIMEOUT) as response:
            raw = response.read(MAX_BYTES + 1)
    except Exception:
        return None
    if len(raw) > MAX_BYTES:
        raw = raw[:MAX_BYTES]
    return raw.decode("utf-8", "replace")


def default_search(query: str) -> List[Dict[str, str]]:
    key = os.environ.get("GOOGLE_CSE_KEY") or ""
    cx = os.environ.get("GOOGLE_CSE_CX") or ""
    if not key or not cx:
        return []
    url = (
        "https://www.googleapis.com/customsearch/v1"
        f"?key={quote(key)}&cx={quote(cx)}&q={quote(query)}&num=3"
    )
    body = default_fetch(url)
    if not body:
        return []
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return []
    found = []
    for item in payload.get("items") or []:
        link = item.get("link") or ""
        if link.startswith("https://"):
            found.append({
                "url": link,
                "title": str(item.get("title") or ""),
                "snippet": str(item.get("snippet") or ""),
            })
    return found


def _html_excerpt(body: str) -> tuple[str, str]:
    title_match = _TITLE_RE.search(body or "")
    title = _SPACE_RE.sub(" ", unescape(title_match.group(1))).strip() if title_match else ""
    text = _TAG_RE.sub(" ", body or "")
    text = _SPACE_RE.sub(" ", unescape(text)).strip()
    return title, text[:1200]


def _chart_quotes(body: str, url: str, country_name: str, assumed: bool) -> List[Dict[str, str]]:
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, dict) or "rows" not in payload:
        return []
    store = "App Store" if payload.get("store") == "app_store" else "Google Play"
    chart_name = {"free": "免费榜", "paid": "付费榜", "grossing": "畅销榜"}.get(payload.get("chart"), str(payload.get("chart") or ""))
    date = str(payload.get("date") or "")
    market = country_name + ("（对话未写市场，取美国总榜）" if assumed else "")
    quotes = []
    for row in (payload.get("rows") or [])[:CHART_ROWS]:
        if not isinstance(row, dict):
            continue
        rank = row.get("curr_rank") or row.get("rank_no")
        name = row.get("name") or ""
        if not name or rank is None:
            continue
        price = row.get("price_amount")
        currency = row.get("price_currency") or row.get("currency") or ""
        rating = row.get("rating")
        rating_count = row.get("rating_count")
        quote = (
            f"{date} {market} {store} {chart_name}第 {rank} 名：{name}，"
            f"开发者 {row.get('developer') or '未知'}，价格 {price} {currency}，"
            f"评分 {rating}（{rating_count} 人）。"
        )
        quotes.append({"quote": quote, "url": url})
    return quotes


def _write_page(workspace: Path, index: List[Dict[str, Any]], *, url: str, title: str, quote: str, kind: str, source_name: str, question: str) -> None:
    sources_dir = workspace / "sources"
    sources_dir.mkdir(parents=True, exist_ok=True)
    page_id = f"s{len(index) + 1}"
    rel = f"sources/{page_id}.md"
    text = f"URL: {url}\n标题: {title or source_name}\n\n{quote}\n"
    (workspace / rel).write_text(text, encoding="utf-8")
    index.append({
        "id": page_id,
        "question": question,
        "quote": quote,
        "kind": kind,
        "source_name": source_name,
        "url": url,
        "path": rel,
    })


def lookup_reliable_sources(
    question: str,
    workspace: Path,
    *,
    catalog: Optional[List[Dict[str, Any]]] = None,
    search: Optional[Search] = None,
    fetch: Optional[Fetch] = None,
) -> Dict[str, Any]:
    """查阅。只把打开后的正文写入 workspace/sources。搜索摘要不进摘录。"""
    workspace = Path(workspace)
    catalog = catalog if catalog is not None else load_catalog()
    search = search if search is not None else default_search
    fetch = fetch if fetch is not None else default_fetch
    question = question or ""
    index: List[Dict[str, Any]] = []
    seen: set[str] = set()
    pages = 0
    attempts = 0

    def take(url: str, *, kind: Optional[str] = None, source_name: str = "", chart_country: str = "", assumed: bool = False) -> None:
        nonlocal pages, attempts
        if pages >= MAX_PAGES or attempts >= 40 or not url.startswith("https://") or url in seen:
            return
        seen.add(url)
        attempts += 1
        body = fetch(url)
        if not body or not body.strip():
            return
        before = len(index)
        source = _match_source(url, catalog)
        page_kind = kind or (source.get("kind") if source else "pasted")
        name = source_name or (source.get("name") if source else "人提供的文章")
        if page_kind == "chart" or "/api/rankings/" in url:
            for item in _chart_quotes(body, url, chart_country, assumed):
                _write_page(
                    workspace, index, url=url, title=name, quote=item["quote"],
                    kind="chart", source_name=name, question=question,
                )
        else:
            title, excerpt = _html_excerpt(body)
            if excerpt:
                _write_page(
                    workspace, index, url=url, title=title or name, quote=excerpt,
                    kind=page_kind or "pasted", source_name=name, question=question,
                )
        if len(index) > before:
            pages += 1

    country, country_name, named = _country(question)
    query = quote(_query_text(question))
    charts = next((item for item in catalog if item.get("kind") == "chart"), None)
    if charts:
        base = str((charts.get("entry_urls") or ["https://e-hai.github.io/Appstore_Top_30/api/"])[0])
        if not base.endswith("/"):
            base += "/"
        dates_body = None
        if attempts < 40:
            attempts += 1
            dates_body = fetch(base + "dates.json")
        latest = ""
        if dates_body:
            try:
                dates = [row.get("date") for row in (json.loads(dates_body).get("dates") or []) if row.get("date")]
                latest = max(dates) if dates else ""
            except json.JSONDecodeError:
                latest = ""
        if latest:
            charts_to_get = ("free", "paid", "grossing")
            stores = ("app_store", "play")
            for store in stores:
                for chart in charts_to_get:
                    take(
                        f"{base}rankings/{store}_{country}_{chart}_{latest}.json",
                        kind="chart", source_name=charts.get("name") or "商店榜单",
                        chart_country=country_name, assumed=not named,
                    )
                    if "游戏" in question:
                        genre = "6014" if store == "app_store" else "GAME"
                        take(
                            f"{base}rankings/{store}_{country}_{chart}_{genre}_{latest}.json",
                            kind="chart", source_name=charts.get("name") or "商店榜单",
                            chart_country=country_name, assumed=not named,
                        )

    kind_order = {"industry": 0, "press": 1, "primary": 2, "store": 3, "policy": 4}
    others = [item for item in catalog if item.get("kind") != "chart"]
    for source in sorted(others, key=lambda item: kind_order.get(item.get("kind"), 9)):
        hosts = source.get("hosts") or []
        candidates: List[str] = []
        if source.get("search"):
            for host in hosts:
                for hit in search(f"{_query_text(question)} site:{host}") or []:
                    url = hit.get("url") or ""
                    if _match_source(url, [source]):
                        candidates.append(url)
        if not candidates:
            for entry in source.get("entry_urls") or []:
                candidates.append(str(entry).replace("{query}", query))
        for url in candidates:
            take(url)

    for url in _URL_RE.findall(question):
        source = _match_source(url, catalog)
        take(url, kind=None if source else "pasted", source_name="" if source else "人提供的文章")

    sources_dir = workspace / "sources"
    sources_dir.mkdir(parents=True, exist_ok=True)
    (sources_dir / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"index": index, "workspace": str(workspace)}


def _index_rows(workspace: Path) -> List[Dict[str, Any]]:
    path = Path(workspace) / "sources" / "index.json"
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def cite(claims: Optional[List[Dict[str, Any]]], workspace: Path) -> List[Dict[str, Any]]:
    """核对。已观测必须对上摘录里的一行，且文件里有同一个 URL。"""
    rows = _index_rows(workspace)
    by_url = {str(row.get("url")): row for row in rows if row.get("url")}
    revised: List[Dict[str, Any]] = []
    for claim in claims or []:
        item = dict(claim)
        status = str(item.get("status") or "")
        if status not in (OBSERVED, "observed"):
            revised.append(item)
            continue
        url = str(item.get("source") or item.get("url") or "")
        row = by_url.get(url)
        page = Path(workspace) / str(row.get("path")) if row else None
        text = ""
        if page and page.is_file():
            try:
                text = page.read_text(encoding="utf-8")
            except OSError:
                text = ""
        if row and url and url in text:
            item["status"] = OBSERVED
        else:
            item["status"] = UNVERIFIED
        revised.append(item)
    return revised


def intake_workspace(draft_id: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_-]", "", draft_id or "")
    if not safe:
        raise ValueError("draft_id")
    path = settings.WORKSPACE_DIR / "_intake" / safe
    path.mkdir(parents=True, exist_ok=True)
    return path


def mount_lookup_tool(workspace: Path) -> None:
    """把查阅工具并进工作区已有的 MCP 配置。核对不挂成工具。"""
    workspace = Path(workspace)
    agents = workspace / ".agents"
    agents.mkdir(parents=True, exist_ok=True)
    server = Path(__file__).resolve().parents[1] / "mcp" / "sources_mcp_server.py"
    entry = {
        "command": sys.executable,
        "args": [str(server), "--workspace", str(workspace.resolve())],
    }
    for path in (agents / "mcp_config.json", workspace / ".mcp.json"):
        payload: Dict[str, Any] = {"mcpServers": {}}
        if path.is_file():
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                loaded = {}
            if isinstance(loaded, dict):
                payload = loaded
        servers = payload.get("mcpServers")
        if not isinstance(servers, dict):
            servers = {}
        servers["moduflow-sources"] = entry
        payload["mcpServers"] = servers
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def prepare_stage_sources(
    workspace: Path,
    question: str,
    *,
    search: Optional[Search] = None,
    fetch: Optional[Fetch] = None,
) -> Dict[str, Any]:
    """派活前查阅一次。失败时也留下空索引，避免没有摘录却放行。"""
    workspace = Path(workspace)
    mount_lookup_tool(workspace)
    try:
        return lookup_reliable_sources(question, workspace, search=search, fetch=fetch)
    except Exception:
        sources = workspace / "sources"
        sources.mkdir(parents=True, exist_ok=True)
        index = sources / "index.json"
        if not index.is_file():
            index.write_text("[]", encoding="utf-8")
        return {"index": [], "workspace": str(workspace)}
