"""工序 06 设计交付包：确定性校验。交付的是可体验的设计稿文件夹，不是文字规范。"""

import json
from pathlib import Path

import pytest

from backend.app.services.deliverable_audit import audit_stage
from backend.app.services.delivery_contract import build_stage_manifest, validate_manifest
from backend.app.services.design_bundle import inspect_design_bundle, upstream_prd_views, validate_design_bundle
from backend.app.services.design_bundle_sim import build_design_bundle, design_manifest_block

VIEWS = ["V-01", "V-02", "V-03", "V-04"]


def _write(root: Path, platform: str = "cross_platform", views=None) -> Path:
    for rel, content in build_design_bundle("演示产品", platform, views).items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return root


def _edit(root: Path, rel: str, old: str, new: str, count: int = -1) -> None:
    path = root / rel
    text = path.read_text(encoding="utf-8")
    assert old in text, f"{rel} 里没有 {old!r}"
    path.write_text(text.replace(old, new, count), encoding="utf-8")


@pytest.mark.parametrize("platform", ["cross_platform", "ios", "android"])
def test_generated_bundle_passes_and_reports_measured_values(tmp_path, platform):
    root = _write(tmp_path, platform)
    reasons, measured = inspect_design_bundle(root, design_manifest_block(platform), platform, VIEWS)
    assert reasons == []
    if platform != "android":
        assert measured["ios_top"] >= 71 and measured["ios_bottom"] >= 34 and measured["ios_touch"] >= 44
    if platform != "ios":
        assert measured["android_top"] >= 24 and measured["android_touch"] >= 48
    if platform == "android":
        assert "ios_top" not in measured  # Android 项目不触发 iOS 检查


def test_manifest_without_files_is_rejected():
    data = json.loads(build_stage_manifest("06", "交付物_06.md"))
    assert validate_manifest(data, platform="cross_platform")  # 没有目录就没有设计包


def test_text_only_deliverable_cannot_pass_stage06():
    res = audit_stage("06", ["# 设计规范\ntop_safe_padding_pt: 74\nmin_touch_target_pt: 44"], platform="ios")
    assert res["passed"] is False
    assert any("设计交付包" in r for r in res["reasons"])


def test_audit_stage_passes_with_bundle_and_exposes_measured_values(tmp_path):
    root = _write(tmp_path)
    (root / "交付物_06.md").write_text("# 设计\nDesign Tokens V-01 V-02 V-03 V-04", encoding="utf-8")
    manifest = build_stage_manifest("06", "交付物_06.md", "cross_platform")
    (root / "delivery.manifest.json").write_text(manifest, encoding="utf-8")
    res = audit_stage("06", [manifest], platform="cross_platform", manifest_root=root)
    assert not [r for r in res["reasons"] if "设计" in r and "工作台" in r]
    assert res["dynamic_island_safe_pt"] == 74
    assert res["min_touch_target_dp"] == 48
    assert res["screens"] == VIEWS


def test_upstream_prd_views_must_all_have_screens(tmp_path):
    stage06 = _write(tmp_path / "06_06_设计实现")
    prd = tmp_path / "05_05_产品需求定义"
    prd.mkdir()
    (prd / "delivery.manifest.json").write_text(json.dumps({"views": VIEWS + ["V-05"]}), encoding="utf-8")
    assert upstream_prd_views(stage06) == VIEWS + ["V-05"]
    reasons = validate_design_bundle(stage06, design_manifest_block("cross_platform"), "cross_platform", upstream_prd_views(stage06))
    assert any("V-05" in r for r in reasons)


def test_color_outside_tokens_is_rejected(tmp_path):
    root = _write(tmp_path)
    _edit(root, "screens/V-01.html", "--color-danger:#DC2626", "--color-danger:#123456")
    reasons = validate_design_bundle(root, design_manifest_block("cross_platform"), "cross_platform", VIEWS)
    assert any("#123456" in r and "tokens.json" in r for r in reasons)


def test_ios_safe_area_below_hig_is_rejected(tmp_path):
    root = _write(tmp_path)
    _edit(root, "screens/V-02.html", 'data-safe-top="74"', 'data-safe-top="50"')
    reasons = validate_design_bundle(root, design_manifest_block("cross_platform"), "cross_platform", VIEWS)
    assert any("V-02" in r and "iOS 顶部安全区" in r for r in reasons)


def test_small_touch_target_and_missing_hit_annotation(tmp_path):
    root = _write(tmp_path)
    _edit(root, "screens/V-03.html", 'data-hit="48x48"', 'data-hit="40x40"', 1)
    _edit(root, "screens/V-04.html", ' data-hit="44x44" data-nav-target="V-03"', ' data-nav-target="V-03"', 1)
    reasons = validate_design_bundle(root, design_manifest_block("cross_platform"), "cross_platform", VIEWS)
    assert any("V-03" in r and "48×48dp" in r for r in reasons)
    assert any("V-04" in r and "data-hit" in r for r in reasons)


def test_missing_state_platform_frame_and_external_dependency(tmp_path):
    root = _write(tmp_path, "ios")
    _edit(root, "screens/V-01.html", 'data-state="error"', 'data-state="oops"')
    _edit(root, "screens/V-02.html", "<script>", '<script src="https://cdn.example.com/x.js"></script><script>', 1)
    reasons = validate_design_bundle(root, design_manifest_block("cross_platform"), "cross_platform", VIEWS)
    assert any("V-01" in r and "error" in r for r in reasons)
    assert any("V-02" in r and "外部资源" in r for r in reasons)
    assert any("android" in r and "设备外框" in r for r in reasons)  # 双端项目缺 Android 画板


def test_broken_navigation_target_is_rejected(tmp_path):
    root = _write(tmp_path)
    _edit(root, "screens/V-01.html", 'data-nav-target="V-02"', 'data-nav-target="V-09"', 1)
    reasons = validate_design_bundle(root, design_manifest_block("cross_platform"), "cross_platform", VIEWS)
    assert any("V-09" in r for r in reasons)


def test_workbench_must_list_every_screen(tmp_path):
    root = _write(tmp_path)
    _edit(root, "index.html", "screens/V-04.html", "screens/gone.html")
    reasons = validate_design_bundle(root, design_manifest_block("cross_platform"), "cross_platform", VIEWS)
    assert any("设计工作台没有收录" in r and "V-04" in r for r in reasons)


def test_missing_tokens_and_icons_are_rejected(tmp_path):
    root = _write(tmp_path)
    (root / "tokens.json").unlink()
    (root / "assets/icons/grid.svg").unlink()
    reasons = validate_design_bundle(root, design_manifest_block("cross_platform"), "cross_platform", VIEWS)
    assert any("tokens_path" in r for r in reasons)
    assert any("grid.svg" in r for r in reasons)


def test_skeleton_page_is_not_a_visual_design(tmp_path):
    root = _write(tmp_path)
    (root / "screens/V-01.html").write_text("<html><body><button>x</button></body></html>", encoding="utf-8")
    reasons = validate_design_bundle(root, design_manifest_block("cross_platform"), "cross_platform", VIEWS)
    assert any("V-01" in r and "完整视觉稿" in r for r in reasons)
