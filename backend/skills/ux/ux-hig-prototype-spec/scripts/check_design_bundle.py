#!/usr/bin/env python3
"""
check_design_bundle.py - Universal Canonical Design Bundle Verification Script

Zero external dependencies (pure Python standard library).
Validates design deliverables produced by any AI harness (Claude Code CLI,
Antigravity, Cursor, ModuFlow Runner) against Sketch MeaXure & HIG/Material standards.

Usage:
    python scripts/check_design_bundle.py [--workspace .] [--platform cross_platform|ios|android] [--json]
"""

import argparse
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET


# ANSI Color Codes
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


class ScreenHTMLParser(HTMLParser):
    """Parses screen HTML to inspect tags, attributes, scripts, and links."""

    def __init__(self):
        super().__init__()
        self.external_links = []
        self.external_scripts = []
        self.has_device_shell_css = False
        self.states_found = set()
        self.hit_targets_found = set()
        self.interactive_elements = []
        self.has_safe_top = False
        self.has_safe_bottom = False
        self.safe_top_values = []
        self.safe_bottom_values = []
        self.tag_stack = []

    def handle_starttag(self, tag, attrs):
        attr_dict = dict(attrs)
        self.tag_stack.append((tag, attr_dict))

        # Check external stylesheets or CSS
        if tag == "link":
            href = attr_dict.get("href", "")
            if href.startswith("http://") or href.startswith("https://") or href.startswith("//"):
                self.external_links.append(href)
            if "device-shell.css" in href:
                self.has_device_shell_css = True

        # Check external scripts
        if tag == "script":
            src = attr_dict.get("src", "")
            if src.startswith("http://") or src.startswith("https://") or src.startswith("//"):
                self.external_scripts.append(src)

        # Check states
        state = attr_dict.get("data-state")
        if state:
            self.states_found.add(state.lower())

        # Check hit targets
        hit = attr_dict.get("data-hit")
        if hit:
            self.hit_targets_found.add(hit)

        # Check safe area annotations
        if "data-safe-top" in attr_dict:
            self.has_safe_top = True
            try:
                self.safe_top_values.append(int(attr_dict["data-safe-top"]))
            except ValueError:
                pass

        if "data-safe-bottom" in attr_dict:
            self.has_safe_bottom = True
            try:
                self.safe_bottom_values.append(int(attr_dict["data-safe-bottom"]))
            except ValueError:
                pass

        # Check interactive elements
        role = attr_dict.get("role", "")
        if tag in ("button", "a", "input", "select") or role in ("button", "link", "tab"):
            self.interactive_elements.append({
                "tag": tag,
                "role": role,
                "hit": hit,
                "class": attr_dict.get("class", ""),
                "id": attr_dict.get("id", "")
            })


def validate_tokens_json(tokens_path: Path):
    errors = []
    warnings = []
    if not tokens_path.is_file():
        return [f"Missing required design tokens file: {tokens_path.name}"], warnings

    try:
        data = json.loads(tokens_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"Invalid JSON in {tokens_path.name}: {exc}"], warnings

    # Check for color tokens
    has_color = False
    for k in data.keys():
        if "color" in k.lower():
            has_color = True
            break
    if not has_color:
        errors.append(f"{tokens_path.name}: Missing 'color' tokens section")

    # Check for spacing or typography tokens
    has_spacing = any("spacing" in k.lower() or "space" in k.lower() for k in data.keys())
    has_type = any("typography" in k.lower() or "font" in k.lower() or "text" in k.lower() for k in data.keys())

    if not has_spacing:
        warnings.append(f"{tokens_path.name}: No explicit 'spacing' tokens found")
    if not has_type:
        warnings.append(f"{tokens_path.name}: No explicit 'typography' tokens found")

    return errors, warnings


def validate_slices(slices_dir: Path):
    errors = []
    warnings = []
    if not slices_dir.is_dir():
        return [f"Missing SVG slices directory: {slices_dir}"], warnings

    svg_files = list(slices_dir.glob("*.svg"))
    if not svg_files:
        return [f"No SVG icons found in {slices_dir}"], warnings

    for svg_file in svg_files:
        try:
            content = svg_file.read_text(encoding="utf-8").strip()
            if not content:
                errors.append(f"Empty SVG slice: {svg_file.name}")
                continue
            tree = ET.fromstring(content)
            if not tree.tag.endswith("svg"):
                errors.append(f"Invalid root tag in {svg_file.name}: expected <svg>, got <{tree.tag}>")
        except Exception as exc:
            errors.append(f"Malformed XML in {svg_file.name}: {exc}")

    return errors, warnings


def validate_screens(screens_dir: Path, platform: str):
    errors = []
    warnings = []

    if not screens_dir.is_dir():
        return [f"Missing screens directory: {screens_dir}"], warnings

    html_files = sorted(list(screens_dir.glob("*.html")))
    if not html_files:
        return [f"No HTML screen files found in {screens_dir}"], warnings

    required_states = {"default", "loading", "empty", "error"}

    for screen_file in html_files:
        content = screen_file.read_text(encoding="utf-8")
        parser = ScreenHTMLParser()
        try:
            parser.feed(content)
        except Exception as exc:
            errors.append(f"{screen_file.name}: HTML parse error: {exc}")
            continue

        # Zero external CDN check
        if parser.external_links:
            errors.append(f"{screen_file.name}: Contains external CDN stylesheets: {', '.join(parser.external_links)}")
        if parser.external_scripts:
            errors.append(f"{screen_file.name}: Contains external CDN scripts: {', '.join(parser.external_scripts)}")

        # Check 4-states
        missing_states = required_states - parser.states_found
        # Also check fallback text if data-state was not used
        if missing_states:
            text_lower = content.lower()
            unresolved = set()
            for s in missing_states:
                if f"state-{s}" not in text_lower and f"state_{s}" not in text_lower and f"state--{s}" not in text_lower:
                    unresolved.add(s)
            if unresolved:
                errors.append(f"{screen_file.name}: Missing design states: {', '.join(sorted(unresolved))}. All 4 states (default, loading, empty, error) required.")

        # Safe area checks based on platform
        check_ios = platform in ("cross_platform", "ios")
        check_android = platform in ("cross_platform", "android")

        # Check iOS safe area (Dynamic Island >= 71pt, bottom >= 34pt)
        if check_ios:
            has_ios_safe = False
            if parser.safe_top_values and any(v >= 71 for v in parser.safe_top_values):
                has_ios_safe = True
            elif "safe-top" in content or "pt-[74px]" in content or "pt-[71px]" in content or "padding-top: 74px" in content or "padding-top: 71px" in content:
                has_ios_safe = True

            if not has_ios_safe:
                errors.append(f"{screen_file.name} (iOS): Top safe area for Dynamic Island (>=71pt) missing or insufficient")

            has_ios_bottom = False
            if parser.safe_bottom_values and any(v >= 34 for v in parser.safe_bottom_values):
                has_ios_bottom = True
            elif "safe-bottom" in content or "pb-[34px]" in content or "padding-bottom: 34px" in content:
                has_ios_bottom = True

            if not has_ios_bottom:
                errors.append(f"{screen_file.name} (iOS): Bottom safe area for Home Indicator (>=34pt) missing or insufficient")

        # Check Android safe area (Punch hole >= 24dp)
        if check_android:
            has_android_safe = False
            if parser.safe_top_values and any(v >= 24 for v in parser.safe_top_values):
                has_android_safe = True
            elif "safe-top-android" in content or "safe-top-punch-hole" in content or "pt-[32px]" in content or "pt-[24px]" in content or "padding-top: 32px" in content or "padding-top: 24px" in content or (check_ios and has_ios_safe):
                # An iOS top safe area >= 71pt also accommodates Android >= 24dp in cross-platform shells
                has_android_safe = True

            if not has_android_safe:
                errors.append(f"{screen_file.name} (Android): Top safe area for status bar/punch-hole (>=24dp) missing or insufficient")

        # Check tap target constraints
        if parser.interactive_elements:
            untagged_interactive = []
            for el in parser.interactive_elements:
                hit = el.get("hit")
                cls = el.get("class", "")
                if not hit:
                    # check class for hit size
                    if "min-w-[44px]" not in cls and "min-h-[44px]" not in cls and "min-w-[48px]" not in cls and "min-h-[48px]" not in cls and "min-h-11" not in cls and "h-11" not in cls and "h-12" not in cls:
                        untagged_interactive.append(f"<{el['tag']}> ({el['id'] or cls.split()[0] if cls else 'unnamed'})")
            if untagged_interactive and len(untagged_interactive) == len(parser.interactive_elements):
                warnings.append(f"{screen_file.name}: Interactive elements without explicit data-hit='44x44' or '48x48': {', '.join(untagged_interactive[:3])}")

    return errors, warnings


def validate_manifest(manifest_path: Path, workspace: Path):
    errors = []
    warnings = []
    if not manifest_path.is_file():
        return [f"Missing manifest file: {manifest_path.name}"], warnings

    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"Invalid JSON in {manifest_path.name}: {exc}"], warnings

    screens = data.get("screens", [])
    if not screens:
        errors.append(f"{manifest_path.name}: 'screens' array is empty or missing")
    else:
        for s in screens:
            s_file = s.get("file")
            s_id = s.get("id")
            if not s_id:
                errors.append(f"{manifest_path.name}: Screen entry missing 'id'")
            if s_file:
                target_path = workspace / s_file
                if not target_path.is_file():
                    errors.append(f"{manifest_path.name}: Screen file does not exist on disk: {s_file}")

    return errors, warnings


def run_checks(workspace: Path, platform: str = "cross_platform"):
    workspace = workspace.resolve()
    all_errors = []
    all_warnings = []

    # 1. Check tokens.json
    tokens_path = workspace / "tokens.json"
    t_err, t_warn = validate_tokens_json(tokens_path)
    all_errors.extend(t_err)
    all_warnings.extend(t_warn)

    # 2. Check slices/ or assets/icons/
    slices_dir = workspace / "slices"
    if not slices_dir.is_dir() and (workspace / "assets" / "icons").is_dir():
        slices_dir = workspace / "assets" / "icons"
    sl_err, sl_warn = validate_slices(slices_dir)
    all_errors.extend(sl_err)
    all_warnings.extend(sl_warn)

    # 3. Check screens/
    screens_dir = workspace / "screens"
    sc_err, sc_warn = validate_screens(screens_dir, platform=platform)
    all_errors.extend(sc_err)
    all_warnings.extend(sc_warn)

    # 4. Check manifest.json
    manifest_path = workspace / "manifest.json"
    if not manifest_path.is_file() and (workspace / "delivery.manifest.json").is_file():
        manifest_path = workspace / "delivery.manifest.json"
    m_err, m_warn = validate_manifest(manifest_path, workspace)
    all_errors.extend(m_err)
    all_warnings.extend(m_warn)

    # 5. Check index.html workbench
    workbench_path = workspace / "index.html"
    if not workbench_path.is_file():
        all_errors.append("Missing interactive workbench entry file: index.html")

    return {
        "passed": len(all_errors) == 0,
        "platform": platform,
        "workspace": str(workspace),
        "errors": all_errors,
        "warnings": all_warnings
    }


def main():
    parser = argparse.ArgumentParser(
        description="Canonical Design Bundle Quality & Stability Linter"
    )
    parser.add_argument(
        "--workspace",
        "-w",
        type=str,
        default=".",
        help="Path to the workspace directory containing design files (default: .)"
    )
    parser.add_argument(
        "--platform",
        "-p",
        type=str,
        default="cross_platform",
        choices=["cross_platform", "ios", "android"],
        help="Target platform specification (default: cross_platform)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON results for CI/harness integration"
    )

    args = parser.parse_args()
    workspace = Path(args.workspace)
    result = run_checks(workspace, platform=args.platform)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        sys.exit(0 if result["passed"] else 1)

    # Terminal UI output
    print(f"\n{BOLD}{CYAN}=== ModuFlow Canonical Design Bundle Validator ==={RESET}")
    print(f"Workspace: {BOLD}{result['workspace']}{RESET}")
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
        print(f"{GREEN}{BOLD}Result: PASSED (All HIG/Material & MeaXure constraints verified){RESET}\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
