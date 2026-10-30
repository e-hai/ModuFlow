import json
from pathlib import Path
import subprocess
import sys
import pytest

from backend.app.services.skill_mcp_mounter import mount_role_skills_and_mcp


SKILL_DIR = Path(__file__).resolve().parents[1] / "skills" / "ux" / "ux-hig-prototype-spec"


def test_ux_skill_templates_and_references_exist():
    """Verify all zero-entropy templates and reference specs exist."""
    assert (SKILL_DIR / "SKILL.md").is_file()

    # Templates
    templates_dir = SKILL_DIR / "templates"
    assert (templates_dir / "tokens.template.json").is_file()
    assert (templates_dir / "device-shell.css").is_file()
    assert (templates_dir / "screen.template.html").is_file()
    assert (templates_dir / "workbench.template.html").is_file()

    # Verify tokens.template.json syntax
    tokens_data = json.loads((templates_dir / "tokens.template.json").read_text(encoding="utf-8"))
    assert "color" in tokens_data
    assert "spacing" in tokens_data

    # Verify device-shell.css contains tap target hard-binding
    css_content = (templates_dir / "device-shell.css").read_text(encoding="utf-8")
    assert '[data-hit="44x44"]' in css_content
    assert '[data-hit="48x48"]' in css_content
    assert "mf-inspect-outline" in css_content

    # References
    ref_dir = SKILL_DIR / "references"
    assert (ref_dir / "component_patterns.md").is_file()
    assert (ref_dir / "meaxure_attributes.md").is_file()

    ref_patterns = (ref_dir / "component_patterns.md").read_text(encoding="utf-8")
    assert "mf-card" in ref_patterns
    assert "mf-chip-bar" in ref_patterns
    assert "mf-skeleton" in ref_patterns

    ref_meaxure = (ref_dir / "meaxure_attributes.md").read_text(encoding="utf-8")
    assert "data-safe-top" in ref_meaxure
    assert "data-nav-target" in ref_meaxure
    assert "mf-pick" in ref_meaxure


def test_check_design_bundle_cli_pass(tmp_path):
    """Verify check_design_bundle.py passes on a fully conforming Canonical Design Bundle."""
    checker_script = SKILL_DIR / "scripts" / "check_design_bundle.py"
    assert checker_script.is_file()

    # Create conforming design workspace
    ws = tmp_path / "valid_bundle"
    ws.mkdir()
    (ws / "screens").mkdir()
    (ws / "slices").mkdir()

    # 1. tokens.json
    (ws / "tokens.json").write_text(json.dumps({
        "color": {"primary": {"value": "#2563eb"}},
        "spacing": {"md": {"value": "16px"}}
    }), encoding="utf-8")

    # 2. slices/
    (ws / "slices" / "icon_check.svg").write_text(
        '<svg viewBox="0 0 24 24"><path d="M5 13l4 4L19 7"/></svg>',
        encoding="utf-8"
    )

    # 3. screens/V-01.html with 4 states and safe areas
    screen_html = """<!DOCTYPE html>
<html>
<head>
  <link rel="stylesheet" href="device-shell.css">
</head>
<body>
  <div id="phone-frame" data-device="ios" data-safe-top="74" data-safe-bottom="34">
    <div class="state-panel is-active" data-state="default">
      <button data-hit="44x44" data-nav-target="V-01">Action</button>
    </div>
    <div class="state-panel" data-state="loading"><div>Loading...</div></div>
    <div class="state-panel" data-state="empty"><div>Empty</div></div>
    <div class="state-panel" data-state="error"><button data-hit="44x44">Retry</button></div>
  </div>
</body>
</html>"""
    (ws / "screens" / "V-01.html").write_text(screen_html, encoding="utf-8")

    # 4. manifest.json
    (ws / "manifest.json").write_text(json.dumps({
        "screens": [{"id": "V-01", "name": "Home", "file": "screens/V-01.html"}],
        "slices": [{"name": "icon_check", "file": "slices/icon_check.svg"}]
    }), encoding="utf-8")

    # 5. index.html
    (ws / "index.html").write_text("<html><body>Workbench</body></html>", encoding="utf-8")

    # Run check_design_bundle.py via CLI
    cmd = [
        sys.executable,
        str(checker_script),
        "--workspace", str(ws),
        "--platform", "cross_platform",
        "--json"
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode == 0, f"Checker failed unexpectedly: {proc.stderr}\n{proc.stdout}"
    data = json.loads(proc.stdout)
    assert data["passed"] is True
    assert len(data["errors"]) == 0


def test_check_design_bundle_cli_fail_on_missing_states_and_cdn(tmp_path):
    """Verify check_design_bundle.py detects missing states and CDN script violations."""
    checker_script = SKILL_DIR / "scripts" / "check_design_bundle.py"

    ws = tmp_path / "invalid_bundle"
    ws.mkdir()
    (ws / "screens").mkdir()
    (ws / "slices").mkdir()

    # Missing color in tokens.json
    (ws / "tokens.json").write_text(json.dumps({"unknown": {}}), encoding="utf-8")

    # Screen with external CDN script and missing loading/empty/error states
    bad_screen = """<!DOCTYPE html>
<html>
<head>
  <script src="https://cdn.example.com/bad-script.js"></script>
</head>
<body>
  <div data-state="default">Only Default State</div>
</body>
</html>"""
    (ws / "screens" / "V-01.html").write_text(bad_screen, encoding="utf-8")

    (ws / "manifest.json").write_text(json.dumps({
        "screens": [{"id": "V-01", "file": "screens/V-01.html"}]
    }), encoding="utf-8")
    (ws / "index.html").write_text("<html></html>", encoding="utf-8")

    cmd = [
        sys.executable,
        str(checker_script),
        "--workspace", str(ws),
        "--platform", "ios",
        "--json"
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode == 1
    data = json.loads(proc.stdout)
    assert data["passed"] is False
    assert any("external CDN" in err for err in data["errors"])
    assert any("Missing design states" in err for err in data["errors"])
    assert any("Dynamic Island" in err for err in data["errors"])


def test_mount_role_skills_mounts_all_templates_and_scripts(tmp_path):
    """Verify mount_role_skills_and_mcp recursively mounts templates, scripts, references."""
    ws = tmp_path / "ws_mount_test"
    info = mount_role_skills_and_mcp(
        workspace_dir=ws,
        primary_role_code="ux",
        platform="cross_platform"
    )

    skill_dest = ws / ".agents" / "skills" / "ux-hig-prototype-spec"
    assert skill_dest.is_dir()
    assert (skill_dest / "SKILL.md").is_file()

    # Scripts
    scripts_dest = skill_dest / "scripts"
    assert (scripts_dest / "check_design_bundle.py").is_file()
    assert (scripts_dest / "check_hig.py").is_file()
    assert (scripts_dest / "check_material.py").is_file()

    # Templates
    templates_dest = skill_dest / "templates"
    assert (templates_dest / "device-shell.css").is_file()
    assert (templates_dest / "workbench.template.html").is_file()
    assert (templates_dest / "screen.template.html").is_file()
    assert (templates_dest / "tokens.template.json").is_file()

    # References
    ref_dest = skill_dest / "references"
    assert (ref_dest / "component_patterns.md").is_file()
    assert (ref_dest / "meaxure_attributes.md").is_file()
