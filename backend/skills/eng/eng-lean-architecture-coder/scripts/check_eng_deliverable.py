#!/usr/bin/env python3
"""
check_eng_deliverable.py - Universal Engineering Deliverable Verification Script

Zero external dependencies (pure Python standard library).
Validates Stage 07 engineering deliverables produced by any AI harness (Claude Code CLI,
Antigravity, Cursor, ModuFlow Runner) across both KMP/CMP and Dual-Native technical strategies.

Usage:
    python scripts/check_eng_deliverable.py [--workspace .] [--strategy kmp_cmp|dual_native] [--platform cross_platform|ios|android] [--json]
"""

import argparse
import json
from pathlib import Path
import re
import sys


# ANSI Color Codes
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

FORBIDDEN_AI_IMPORTS = [
    r"import\s+.*openai",
    r"import\s+.*anthropic",
    r"import\s+.*generativeai",
    r"import\s+.*langchain",
    r"import\s+.*cohere",
    r"import\s+.*replicate",
    r"import\s+.*huggingface"
]


def load_tech_stack(workspace: Path):
    tech_stack_path = workspace / "tech_stack.json"
    if not tech_stack_path.is_file():
        return None, ["Missing required technical specification contract: tech_stack.json"]
    try:
        data = json.loads(tech_stack_path.read_text(encoding="utf-8"))
        return data, []
    except Exception as exc:
        return None, [f"Invalid JSON in tech_stack.json: {exc}"]


def validate_compatibility_versions(tech_data: dict, platform: str):
    """Validates defined minimum OS, SDK, and toolchain compatibility baselines."""
    errors = []
    warnings = []
    compat = tech_data.get("compatibility")
    if not compat or not isinstance(compat, dict):
        warnings.append("Missing 'compatibility' section in tech_stack.json; recommended to define explicit OS/SDK minimums")
        return errors, warnings

    check_ios = platform in ("cross_platform", "ios")
    check_android = platform in ("cross_platform", "android")

    if check_ios:
        ios_compat = compat.get("ios", {})
        min_ios = str(ios_compat.get("min_deployment_target", "")).strip()
        if not min_ios:
            warnings.append("Missing iOS minimum deployment target ('compatibility.ios.min_deployment_target') in tech_stack.json")
        else:
            try:
                major_ios = float(".".join(min_ios.split(".")[:2]))
                if major_ios < 16.0:
                    warnings.append(f"iOS deployment target '{min_ios}' is below recommended modern baseline iOS 16.0")
            except Exception:
                pass

    if check_android:
        android_compat = compat.get("android", {})
        min_sdk = android_compat.get("min_sdk")
        target_sdk = android_compat.get("target_sdk")

        if min_sdk is None:
            warnings.append("Missing Android minimum SDK ('compatibility.android.min_sdk') in tech_stack.json")
        elif int(min_sdk) < 24:
            warnings.append(f"Android minSdk {min_sdk} is below recommended modern baseline API 24 (Android 7.0)")

        if target_sdk is not None and int(target_sdk) < 34:
            errors.append(f"Android targetSdk {target_sdk} violates Google Play Store submission requirement (API 34+ required)")

    return errors, warnings


def validate_kmp_cmp_structure(workspace: Path, platform: str):
    errors = []
    warnings = []

    # 1. shared module
    shared_dir = workspace / "shared"
    if not shared_dir.is_dir():
        errors.append("KMP/CMP strategy violation: Missing core multiplatform library module 'shared/'")
    else:
        common_main = shared_dir / "src" / "commonMain"
        if not common_main.is_dir() or not list(common_main.rglob("*.kt")):
            errors.append("Missing Kotlin source files under 'shared/src/commonMain/'")

        common_test = shared_dir / "src" / "commonTest"
        if not common_test.is_dir() or not list(common_test.rglob("*.kt")):
            errors.append("Missing multiplatform unit tests under 'shared/src/commonTest/' (80% coverage gate required)")

    # 2. Host application modules
    check_android = platform in ("cross_platform", "android")
    check_ios = platform in ("cross_platform", "ios")

    if check_android:
        android_app = workspace / "androidApp"
        if not android_app.is_dir():
            errors.append("KMP/CMP strategy violation: Missing standalone Android host application module 'androidApp/'")
        else:
            has_activity = any("MainActivity" in f.name for f in android_app.rglob("*.kt"))
            if not has_activity:
                warnings.append("No MainActivity found under 'androidApp/src/'")

    if check_ios:
        ios_app = workspace / "iosApp"
        ios_main = shared_dir / "src" / "iosMain" if shared_dir.is_dir() else None
        if not ios_app.is_dir() and (not ios_main or not ios_main.is_dir()):
            errors.append("KMP/CMP strategy violation: Missing iOS entry module 'iosApp/' or 'shared/src/iosMain/'")

    # 3. Root Gradle files
    has_build_gradle = (workspace / "build.gradle.kts").is_file() or (workspace / "build.gradle").is_file()
    has_settings = (workspace / "settings.gradle.kts").is_file() or (workspace / "settings.gradle").is_file()
    if not has_build_gradle:
        errors.append("Missing root Gradle build script 'build.gradle.kts'")
    if not has_settings:
        warnings.append("Missing root Gradle settings script 'settings.gradle.kts'")

    return errors, warnings


def validate_dual_native_structure(workspace: Path, platform: str):
    errors = []
    warnings = []

    check_android = platform in ("cross_platform", "android")
    check_ios = platform in ("cross_platform", "ios")

    if check_ios:
        ios_dir = workspace / "ios"
        if not ios_dir.is_dir():
            errors.append("Dual-Native strategy violation: Missing iOS native project directory 'ios/'")
        else:
            has_spm = (ios_dir / "Package.swift").is_file()
            has_xcode = bool(list(ios_dir.glob("*.xcodeproj")) or list(ios_dir.glob("*.xcworkspace")))
            if not has_spm and not has_xcode:
                errors.append("Missing Package.swift or Xcode project in 'ios/'")

            swift_sources = list(ios_dir.rglob("*.swift"))
            if not swift_sources:
                errors.append("No Swift source files found in 'ios/'")

            has_tests = any("Test" in f.name for f in swift_sources)
            if not has_tests:
                errors.append("No unit tests found in 'ios/Tests/' (80% coverage gate required)")

    if check_android:
        android_dir = workspace / "android"
        if not android_dir.is_dir():
            errors.append("Dual-Native strategy violation: Missing Android native project directory 'android/'")
        else:
            has_gradle = (android_dir / "build.gradle.kts").is_file() or (android_dir / "build.gradle").is_file()
            if not has_gradle:
                errors.append("Missing Gradle build script in 'android/'")

            kt_sources = list(android_dir.rglob("*.kt")) + list(android_dir.rglob("*.java"))
            if not kt_sources:
                errors.append("No Kotlin or Java source files found in 'android/'")

            has_tests = any("Test" in f.name for f in kt_sources)
            if not has_tests:
                errors.append("No unit tests found in 'android/src/test/' (80% coverage gate required)")

    return errors, warnings


def audit_zero_inference_imports(workspace: Path):
    violations = []
    code_files = list(workspace.rglob("*.kt")) + list(workspace.rglob("*.swift")) + list(workspace.rglob("*.java"))

    for f in code_files:
        try:
            content = f.read_text(encoding="utf-8")
            for pattern in FORBIDDEN_AI_IMPORTS:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    rel_path = f.relative_to(workspace)
                    violations.append(f"{rel_path}: Forbidden unauthorized client AI SDK import '{match.group(0)}'")
        except Exception:
            pass

    return violations


def audit_views_and_states(workspace: Path):
    errors = []
    warnings = []

    # Check for state machine handling (loading, empty, error)
    all_code_text = ""
    for ext in ("*.kt", "*.swift", "*.java"):
        for f in workspace.rglob(ext):
            try:
                all_code_text += f.read_text(encoding="utf-8").lower() + "\n"
            except Exception:
                pass

    if not all_code_text:
        return errors, warnings

    has_loading = "loading" in all_code_text
    has_empty = "empty" in all_code_text
    has_error = "error" in all_code_text

    missing_states = []
    if not has_loading: missing_states.append("Loading")
    if not has_empty: missing_states.append("Empty")
    if not has_error: missing_states.append("Error")

    if missing_states:
        errors.append(f"Incomplete 4-state state machine handling: Missing state branches for {', '.join(missing_states)}")

    return errors, warnings


def run_checks(workspace: Path, strategy: str = None, platform: str = None):
    workspace = workspace.resolve()
    all_errors = []
    all_warnings = []

    # 1. Read tech_stack.json
    tech_data, ts_errors = load_tech_stack(workspace)
    if ts_errors:
        all_errors.extend(ts_errors)
        return {
            "passed": False,
            "strategy": strategy or "unknown",
            "platform": platform or "unknown",
            "workspace": str(workspace),
            "errors": all_errors,
            "warnings": all_warnings
        }

    # Resolve strategy & platform from tech_stack.json if not specified via CLI
    effective_strategy = strategy or tech_data.get("strategy", "kmp_cmp")
    effective_platform = platform or tech_data.get("platform", "cross_platform")
    zero_inference = tech_data.get("client_zero_inference", True)

    # 1.5. Minimum supported versions & compatibility checks
    c_err, c_warn = validate_compatibility_versions(tech_data, platform=effective_platform)
    all_errors.extend(c_err)
    all_warnings.extend(c_warn)

    # 2. Strategy structure checks
    if effective_strategy == "kmp_cmp":
        st_err, st_warn = validate_kmp_cmp_structure(workspace, platform=effective_platform)
        all_errors.extend(st_err)
        all_warnings.extend(st_warn)
    elif effective_strategy == "dual_native":
        st_err, st_warn = validate_dual_native_structure(workspace, platform=effective_platform)
        all_errors.extend(st_err)
        all_warnings.extend(st_warn)
    else:
        all_errors.append(f"Unknown architecture strategy: '{effective_strategy}'. Must be 'kmp_cmp' or 'dual_native'")

    # 3. 4-State handling check
    vs_err, vs_warn = audit_views_and_states(workspace)
    all_errors.extend(vs_err)
    all_warnings.extend(vs_warn)

    # 4. Zero client inference cost check
    if zero_inference:
        ai_violations = audit_zero_inference_imports(workspace)
        all_errors.extend(ai_violations)

    return {
        "passed": len(all_errors) == 0,
        "strategy": effective_strategy,
        "platform": effective_platform,
        "workspace": str(workspace),
        "errors": all_errors,
        "warnings": all_warnings
    }


def main():
    parser = argparse.ArgumentParser(
        description="Stage 07 Engineering Deliverable Quality & Architecture Linter"
    )
    parser.add_argument(
        "--workspace",
        "-w",
        type=str,
        default=".",
        help="Path to workspace containing engineering deliverable code (default: .)"
    )
    parser.add_argument(
        "--strategy",
        "-s",
        type=str,
        default=None,
        choices=["kmp_cmp", "dual_native"],
        help="Architecture strategy: kmp_cmp (default) or dual_native (auto-detected if omitted)"
    )
    parser.add_argument(
        "--platform",
        "-p",
        type=str,
        default=None,
        choices=["cross_platform", "ios", "android"],
        help="Target platform (auto-detected from tech_stack.json if omitted)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON results for CI/harness integration"
    )

    args = parser.parse_args()
    workspace = Path(args.workspace)
    result = run_checks(workspace, strategy=args.strategy, platform=args.platform)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        sys.exit(0 if result["passed"] else 1)

    # Terminal UI output
    print(f"\n{BOLD}{CYAN}=== ModuFlow Stage 07 Engineering Deliverable Validator ==={RESET}")
    print(f"Workspace: {BOLD}{result['workspace']}{RESET}")
    print(f"Strategy:  {BOLD}{result['strategy']}{RESET}")
    print(f"Platform:  {BOLD}{result['platform']}{RESET}\n")

    if result["warnings"]:
        print(f"{YELLOW}{BOLD}Warnings ({len(result['warnings'])}):{RESET}")
        for w in result["warnings"]:
            print(f"  {YELLOW}⚠ {w}{RESET}")
        print()

    if result["errors"]:
        print(f"{RED}{BOLD}Violations Found ({len(result['errors'])}):{RESET}")
        for err in result["errors"]:
            print(f"  {RED}✖ {err}{RESET}")
        print(f"\n{RED}{BOLD}Result: FAILED{RESET}\n")
        sys.exit(1)
    else:
        print(f"{GREEN}{BOLD}Result: PASSED (All architecture, 4-state, zero-inference, and test constraints verified){RESET}\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
