import json
from pathlib import Path
import subprocess
import sys
import pytest

from backend.app.services.skill_mcp_mounter import mount_role_skills_and_mcp


SKILL_DIR = Path(__file__).resolve().parents[1] / "skills" / "eng" / "eng-lean-architecture-coder"


def test_eng_skill_templates_and_references_exist():
    """Verify all zero-entropy templates and architecture strategy references exist."""
    assert (SKILL_DIR / "SKILL.md").is_file()

    # KMP / CMP Templates (JetBrains New Default Structure)
    kmp_dir = SKILL_DIR / "templates" / "kmp_cmp"
    assert (kmp_dir / "tech_stack.template.json").is_file()
    assert (kmp_dir / "build.gradle.kts.template").is_file()
    assert (kmp_dir / "settings.gradle.kts.template").is_file()
    assert (kmp_dir / "gradle" / "libs.versions.toml.template").is_file()
    assert (kmp_dir / "shared" / "build.gradle.kts.template").is_file()
    assert (kmp_dir / "shared" / "Tokens.kt.template").is_file()
    assert (kmp_dir / "shared" / "StateViewModel.kt.template").is_file()
    assert (kmp_dir / "androidApp" / "build.gradle.kts.template").is_file()
    assert (kmp_dir / "androidApp" / "MainActivity.kt.template").is_file()
    assert (kmp_dir / "iosApp" / "iOSApp.swift.template").is_file()

    # Verify KMP tech stack syntax
    kmp_ts = json.loads((kmp_dir / "tech_stack.template.json").read_text(encoding="utf-8"))
    assert kmp_ts["strategy"] == "kmp_cmp"
    assert kmp_ts["client_zero_inference"] is True

    # Dual-Native Templates
    native_dir = SKILL_DIR / "templates" / "dual_native"
    assert (native_dir / "tech_stack.template.json").is_file()
    assert (native_dir / "ios" / "Package.swift.template").is_file()
    assert (native_dir / "ios" / "Tokens.swift.template").is_file()
    assert (native_dir / "android" / "build.gradle.kts.template").is_file()
    assert (native_dir / "android" / "Tokens.kt.template").is_file()

    native_ts = json.loads((native_dir / "tech_stack.template.json").read_text(encoding="utf-8"))
    assert native_ts["strategy"] == "dual_native"

    # References
    ref_file = SKILL_DIR / "references" / "architecture_strategies.md"
    assert ref_file.is_file()
    ref_content = ref_file.read_text(encoding="utf-8")
    assert "kmp_cmp" in ref_content
    assert "dual_native" in ref_content
    assert "UiState" in ref_content


def test_check_eng_deliverable_cli_pass_kmp_cmp(tmp_path):
    """Verify check_eng_deliverable.py passes on a fully conforming KMP/CMP workspace."""
    checker_script = SKILL_DIR / "scripts" / "check_eng_deliverable.py"
    assert checker_script.is_file()

    ws = tmp_path / "kmp_bundle"
    ws.mkdir()

    # 1. tech_stack.json
    (ws / "tech_stack.json").write_text(json.dumps({
        "contract_version": "1.0",
        "strategy": "kmp_cmp",
        "platform": "cross_platform",
        "client_zero_inference": True
    }), encoding="utf-8")

    # 2. Root scripts
    (ws / "build.gradle.kts").write_text("// root build script", encoding="utf-8")
    (ws / "settings.gradle.kts").write_text('include(":shared", ":androidApp")', encoding="utf-8")

    # 3. shared module with 4 states & tests
    shared_main = ws / "shared" / "src" / "commonMain" / "kotlin" / "com" / "moduflow"
    shared_main.mkdir(parents=True)
    shared_test = ws / "shared" / "src" / "commonTest" / "kotlin" / "com" / "moduflow"
    shared_test.mkdir(parents=True)

    code_content = """
    package com.moduflow
    sealed interface UiState<out T> {
        object Loading : UiState<Nothing>
        object Empty : UiState<Nothing>
        data class Error(val msg: String) : UiState<Nothing>
        data class Ready<T>(val data: T) : UiState<T>
    }
    class HomeViewModel {
        fun load() {}
    }
    """
    (shared_main / "HomeViewModel.kt").write_text(code_content, encoding="utf-8")
    (shared_test / "HomeViewModelTest.kt").write_text(
        "package com.moduflow\nimport kotlin.test.Test\nclass HomeTest { @Test fun testOk() {} }",
        encoding="utf-8"
    )

    # 4. androidApp and iosApp
    android_app = ws / "androidApp" / "src" / "main" / "kotlin" / "com" / "moduflow" / "app"
    android_app.mkdir(parents=True)
    (android_app / "MainActivity.kt").write_text("package com.moduflow.app\nclass MainActivity", encoding="utf-8")

    ios_app = ws / "iosApp"
    ios_app.mkdir()
    (ios_app / "iOSApp.swift").write_text("import SwiftUI\nstruct iOSApp {}", encoding="utf-8")

    # Execute checker
    cmd = [
        sys.executable,
        str(checker_script),
        "--workspace", str(ws),
        "--json"
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode == 0, f"Checker failed: {proc.stderr}\n{proc.stdout}"
    data = json.loads(proc.stdout)
    assert data["passed"] is True
    assert data["strategy"] == "kmp_cmp"
    assert len(data["errors"]) == 0


def test_check_eng_deliverable_cli_pass_dual_native(tmp_path):
    """Verify check_eng_deliverable.py passes on a conforming Dual-Native workspace."""
    checker_script = SKILL_DIR / "scripts" / "check_eng_deliverable.py"

    ws = tmp_path / "native_bundle"
    ws.mkdir()

    (ws / "tech_stack.json").write_text(json.dumps({
        "contract_version": "1.0",
        "strategy": "dual_native",
        "platform": "cross_platform",
        "client_zero_inference": True
    }), encoding="utf-8")

    # iOS
    ios_dir = ws / "ios"
    (ios_dir / "Sources").mkdir(parents=True)
    (ios_dir / "Tests").mkdir(parents=True)
    (ios_dir / "Package.swift").write_text("// Package.swift", encoding="utf-8")
    ios_code = """
    enum ViewState { case loading, empty, error(String), ready }
    class AppViewModel {}
    """
    (ios_dir / "Sources" / "App.swift").write_text(ios_code, encoding="utf-8")
    (ios_dir / "Tests" / "AppTests.swift").write_text("import XCTest\nclass AppTests {}", encoding="utf-8")

    # Android
    android_dir = ws / "android"
    android_src = android_dir / "src" / "main" / "kotlin"
    android_src.mkdir(parents=True)
    android_test = android_dir / "src" / "test" / "kotlin"
    android_test.mkdir(parents=True)
    (android_dir / "build.gradle.kts").write_text("// build", encoding="utf-8")
    (android_src / "MainActivity.kt").write_text("class MainActivity", encoding="utf-8")
    (android_test / "MainTest.kt").write_text("class MainTest", encoding="utf-8")

    cmd = [
        sys.executable,
        str(checker_script),
        "--workspace", str(ws),
        "--json"
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode == 0, f"Checker failed: {proc.stderr}\n{proc.stdout}"
    data = json.loads(proc.stdout)
    assert data["passed"] is True
    assert data["strategy"] == "dual_native"


def test_check_eng_deliverable_cli_detects_forbidden_ai_sdk_and_missing_states(tmp_path):
    """Verify check_eng_deliverable.py catches unauthorized AI SDK imports and missing 4-state flow."""
    checker_script = SKILL_DIR / "scripts" / "check_eng_deliverable.py"

    ws = tmp_path / "violating_bundle"
    ws.mkdir()

    (ws / "tech_stack.json").write_text(json.dumps({
        "contract_version": "1.0",
        "strategy": "kmp_cmp",
        "platform": "cross_platform",
        "client_zero_inference": True
    }), encoding="utf-8")

    (ws / "build.gradle.kts").write_text("// build", encoding="utf-8")
    shared_main = ws / "shared" / "src" / "commonMain" / "kotlin"
    shared_main.mkdir(parents=True)
    shared_test = ws / "shared" / "src" / "commonTest" / "kotlin"
    shared_test.mkdir(parents=True)
    (shared_test / "Test.kt").write_text("class Test", encoding="utf-8")

    # Code violating zero client inference (calling OpenAI SDK directly) and missing empty/error states
    bad_code = """
    package com.moduflow
    import com.aallam.openai.client.OpenAI
    class SecretAIAgent {
        val client = OpenAI("sk-bad")
    }
    """
    (shared_main / "BadService.kt").write_text(bad_code, encoding="utf-8")

    cmd = [
        sys.executable,
        str(checker_script),
        "--workspace", str(ws),
        "--json"
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode == 1
    data = json.loads(proc.stdout)
    assert data["passed"] is False
    assert any("Forbidden unauthorized client AI SDK import" in err for err in data["errors"])
    assert any("Incomplete 4-state state machine" in err for err in data["errors"])


def test_check_eng_deliverable_compatibility_gate(tmp_path):
    """Verify check_eng_deliverable.py enforces Google Play targetSdk >= 34 gate."""
    checker_script = SKILL_DIR / "scripts" / "check_eng_deliverable.py"
    ws = tmp_path / "legacy_target_bundle"
    ws.mkdir()

    # Legacy target_sdk = 30 violates Google Play Store submission requirement
    (ws / "tech_stack.json").write_text(json.dumps({
        "contract_version": "1.0",
        "strategy": "kmp_cmp",
        "platform": "cross_platform",
        "client_zero_inference": True,
        "compatibility": {
            "android": {
                "min_sdk": 21,
                "target_sdk": 30
            }
        }
    }), encoding="utf-8")

    cmd = [
        sys.executable,
        str(checker_script),
        "--workspace", str(ws),
        "--json"
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode == 1
    data = json.loads(proc.stdout)
    assert data["passed"] is False
    assert any("Google Play Store submission requirement" in err for err in data["errors"])
    assert any("below recommended modern baseline API 24" in w for w in data["warnings"])


def test_mount_role_skills_mounts_eng_templates_and_scripts(tmp_path):
    """Verify mount_role_skills_and_mcp recursively mounts templates, scripts, references for ENG."""
    ws = tmp_path / "ws_eng_mount_test"
    info = mount_role_skills_and_mcp(
        workspace_dir=ws,
        primary_role_code="eng",
        client_zero_inference=True
    )

    skill_dest = ws / ".agents" / "skills" / "eng-lean-architecture-coder"
    assert skill_dest.is_dir()
    assert (skill_dest / "SKILL.md").is_file()

    # Scripts
    scripts_dest = skill_dest / "scripts"
    assert (scripts_dest / "check_eng_deliverable.py").is_file()
    assert (scripts_dest / "cost_audit.py").is_file()

    # Templates
    templates_dest = skill_dest / "templates"
    assert (templates_dest / "kmp_cmp" / "tech_stack.template.json").is_file()
    assert (templates_dest / "kmp_cmp" / "shared" / "Tokens.kt.template").is_file()
    assert (templates_dest / "dual_native" / "tech_stack.template.json").is_file()

    # References
    ref_dest = skill_dest / "references"
    assert (ref_dest / "architecture_strategies.md").is_file()
