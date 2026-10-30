"""
测试 DesignAdapter (设计资产适配层) 与 MeaXure 标准规范

验证：
1. SketchMeaXureAdapter: 解析 Sketch MeaXure 导出 zip 与解压目录，正确提取色彩生成 tokens.json、对齐 slices/、编译 screens/ 并通过确定性门禁
2. NativeAIAgentAdapter: 规范化补齐 AI 生成的画板与设计工作台
3. 适配后的 Canonical Design Bundle 100% 通过 design_bundle.py 静态核验
4. role_mcp_server 的 verify_design_bundle MCP 工具可用且准确
"""
import io
import json
import zipfile
from pathlib import Path

import pytest

from backend.app.mcp.role_mcp_server import execute_role_tool
from backend.app.services.design_adapter import (
    NativeAIAgentAdapter,
    SketchMeaXureAdapter,
    adapt_to_canonical_bundle,
    resolve_design_adapter,
)
from backend.app.services.design_bundle import inspect_design_bundle
from backend.app.services.design_bundle_sim import ICONS, build_design_bundle, icon_svg


def _create_mock_meaxure_zip(zip_path: Path) -> Path:
    """创建模拟的 Sketch MeaXure 导出压缩包"""
    manifest_data = {
        "project": "ScanCraft UI",
        "scale": 3,
        "unit": "pt",
        "colors": [
            {"name": "Brand Green", "hex": "#0E8A5A"},
            {"name": "Dark Green", "hex": "#0A6B46"},
            {"name": "Soft Green", "hex": "#E3F4EC"},
            {"name": "Background", "hex": "#F8FAFC"},
            {"name": "Surface", "hex": "#FFFFFF"},
            {"name": "Primary Text", "hex": "#0F172A"},
            {"name": "Muted Text", "hex": "#64748B"},
            {"name": "Border Gray", "hex": "#E2E8F0"},
            {"name": "Danger Red", "hex": "#DC2626"},
            {"name": "Danger Soft", "hex": "#FEE2E2"},
            {"name": "Stage Dark", "hex": "#1E293B"},
        ],
        "artboards": [
            {"name": "V-01 模板首页", "slug": "v-01", "width": 393, "height": 852},
            {"name": "V-02 创作编辑", "slug": "v-02", "width": 393, "height": 852},
            {"name": "V-03 结果预览", "slug": "v-03", "width": 393, "height": 852},
            {"name": "V-04 历史归档", "slug": "v-04", "width": 393, "height": 852},
        ],
    }
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest_data, ensure_ascii=False))
        zf.writestr("index.html", "<html><body>MeaXure Viewer Mock</body></html>")
        for icon in ["grid", "plus", "history", "check"]:
            zf.writestr(f"slices/{icon}.svg", icon_svg(icon))
    return zip_path


def test_sketch_meaxure_adapter_can_adapt_zip(tmp_path):
    zip_file = tmp_path / "meaxure_export.zip"
    _create_mock_meaxure_zip(zip_file)

    adapter = resolve_design_adapter(zip_file)
    assert isinstance(adapter, SketchMeaXureAdapter)
    assert adapter.can_adapt(zip_file) is True


def test_sketch_meaxure_adapter_compiles_to_canonical_bundle(tmp_path):
    zip_file = tmp_path / "meaxure_export.zip"
    _create_mock_meaxure_zip(zip_file)

    target_dir = tmp_path / "06_canonical_bundle"
    res = adapt_to_canonical_bundle(
        source_path=zip_file,
        target_dir=target_dir,
        product_name="ScanCraft",
        platform="cross_platform",
        views=["V-01", "V-02", "V-03", "V-04"],
    )

    assert res["adapter"] == "SketchMeaXureAdapter"
    assert (target_dir / "index.html").is_file()
    assert (target_dir / "tokens.json").is_file()
    assert (target_dir / "manifest.json").is_file()
    assert (target_dir / "delivery.manifest.json").is_file()
    assert (target_dir / "slices" / "grid.svg").is_file()
    assert (target_dir / "screens" / "V-01.html").is_file()
    assert (target_dir / "screens" / "V-04.html").is_file()

    # 验证提取的色彩已注入 tokens.json
    tokens = json.loads((target_dir / "tokens.json").read_text(encoding="utf-8"))
    assert tokens["color"]["brand_green"] == "#0E8A5A"

    # 验证导出的交付包 100% 通过确定性静态门禁
    delivery_manifest = json.loads((target_dir / "delivery.manifest.json").read_text(encoding="utf-8"))
    reasons, measured = inspect_design_bundle(
        root=target_dir,
        design=delivery_manifest["design"],
        platform="cross_platform",
        upstream_views=["V-01", "V-02", "V-03", "V-04"],
    )
    assert reasons == [], f"Adapted MeaXure bundle failed audit: {reasons}"
    assert measured.get("ios_top") >= 71
    assert measured.get("android_top") >= 24


def test_native_ai_agent_adapter_compiles_cleanly(tmp_path):
    source_dir = tmp_path / "ai_raw_workspace"
    source_dir.mkdir()
    # 模拟 AI Agent 原生生成的文件
    for rel, content in build_design_bundle("AI设计测试", "cross_platform").items():
        dest = source_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")

    adapter = resolve_design_adapter(source_dir)
    assert isinstance(adapter, NativeAIAgentAdapter)

    target_dir = tmp_path / "ai_canonical_bundle"
    res = adapter.adapt(
        source_path=source_dir,
        target_dir=target_dir,
        product_name="AI设计测试",
        platform="cross_platform",
        views=["V-01", "V-02", "V-03", "V-04"],
    )
    assert res["adapter"] == "NativeAIAgentAdapter"
    assert (target_dir / "delivery.manifest.json").is_file()
    assert (target_dir / "manifest.json").is_file()
    assert (target_dir / "slices" / "plus.svg").is_file()

    delivery_manifest = json.loads((target_dir / "delivery.manifest.json").read_text(encoding="utf-8"))
    reasons, measured = inspect_design_bundle(
        root=target_dir,
        design=delivery_manifest["design"],
        platform="cross_platform",
        upstream_views=["V-01", "V-02", "V-03", "V-04"],
    )
    assert reasons == [], f"AI Agent adapted bundle failed audit: {reasons}"


def test_mcp_verify_design_bundle_tool(tmp_path):
    # 1. 在工作区中准备标准设计包
    for rel, content in build_design_bundle("MCP自检测试", "cross_platform").items():
        dest = tmp_path / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
    (tmp_path / "delivery.manifest.json").write_text(
        json.dumps(
            {
                "contract_version": "1",
                "stage": "06",
                "artifacts": [{"role": "design_workbench", "path": "index.html"}],
                "risk_flags": {},
                "design": {
                    "platform": "cross_platform",
                    "entry": "index.html",
                    "tokens_path": "tokens.json",
                    "screens": [
                        {"view_id": v, "path": f"screens/{v}.html", "platforms": ["ios", "android"]}
                        for v in ("V-01", "V-02", "V-03", "V-04")
                    ],
                    "slices": [f"slices/{i}.svg" for i in ICONS],
                },
            }
        ),
        encoding="utf-8",
    )

    # 2. 调用 MCP 工具自检
    res = execute_role_tool(
        role_code="ux",
        workspace_dir=tmp_path,
        tool_name="verify_design_bundle",
        args={"platform": "cross_platform"},
    )

    assert res["passed"] is True
    assert res["errors"] == []
    assert res["measured"]["ios_top"] >= 71
    assert "通过" in res["advice"]

    # 3. 故意破坏一个画板（引入未登记色值），验证即时报错
    screen1 = tmp_path / "screens" / "V-01.html"
    screen1_text = screen1.read_text(encoding="utf-8")
    screen1.write_text(screen1_text.replace("#DC2626", "#00FFAB"), encoding="utf-8")

    res_fail = execute_role_tool(
        role_code="ux",
        workspace_dir=tmp_path,
        tool_name="verify_design_bundle",
        args={"platform": "cross_platform"},
    )
    assert res_fail["passed"] is False
    assert any("#00ffab" in err and "tokens.json" in err for err in res_fail["errors"])
