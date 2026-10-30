---
name: ux-hig-prototype-spec
description: >-
  Universal Stage 06 (Design Implementation) skill for any AI agent harness (Claude Code CLI, Antigravity, Cursor, ModuFlow Runner). Generates production-grade, interactive Sketch MeaXure Canonical Design Bundles with tokens.json, SVG icon slices, 4-state mobile artboards, and HIG/Material safe-area enforcement.
---

# Universal UX Design Bundle Specification (ux-hig-prototype-spec)

This skill instructs an AI agent harness (Claude Code CLI, Antigravity/`agy`, Cursor, or ModuFlow daemon) to reliably architect, generate, and verify **high-fidelity Canonical Design Bundles** matching industrial Sketch MeaXure standards.

---

## Deliverable Architecture (Directory Standard)

A valid Stage 06 deliverable workspace MUST contain the following files:

```
workspace/
├── index.html                   # MeaXure-style 3-column interactive inspection workbench
├── manifest.json                # Screen list, slice registry, and metadata
├── tokens.json                  # W3C design tokens (colors, spacing, typography)
├── screens/
│   ├── device-shell.css         # Physical frame layout, safe areas & inspection overlays
│   ├── V-01.html                # Artboard 1 (with 4 states: default, loading, empty, error)
│   ├── V-02.html                # Artboard 2
│   └── ...                      # One HTML per PRD view (V-01~V-xx)
└── slices/                      # Standalone vector icon and illustration assets
    ├── icon_scan.svg
    ├── icon_settings.svg
    └── ...
```

---

## 3-Phase Progressive Protocol

### Phase 1: Structure & Tokens Initialization

1. **Extract PRD Specification**:
   Read the upstream PRD (from `delivery.manifest.json` or Stage 05 output).
   Extract all view codes (`V-01~V-xx`), core workflows, and commercial pricing tiers.
2. **Initialize Design Tokens**:
   Copy `templates/tokens.template.json` to `./tokens.json`.
   Customize the primary brand color, surface background, typography scale, and spacing tokens.
3. **Initialize SVG Assets**:
   Create the `./slices/` folder.
   Generate clean standalone `<svg>` icons for all app actions (back, close, search, scan, check, chevron).
   **Absolute Rule: Zero external CDN fonts or icon libraries allowed (FontAwesome, Google Fonts, etc.)**.
4. **Initialize Shell & Workbench**:
   - Copy `templates/device-shell.css` to `./screens/device-shell.css`.
   - Copy `templates/workbench.template.html` to `./index.html`.
5. **Initialize Metadata**:
   Create `./manifest.json` listing all screens with `id`, `name`, `file`, and slice definitions.

---

### Phase 2: High-Fidelity Multi-State Artboard Generation

For every PRD view (`V-01`, `V-02`, ...):
1. **Scaffold Artboard**:
   Copy `templates/screen.template.html` to `./screens/{view_id}.html`.
2. **Implement 4 Design States**:
   Every screen file MUST implement all four distinct states in separate panel containers:
   - `data-state="default"`: Full operational screen with rich realistic sample data.
   - `data-state="loading"`: Skeleton pulse shimmer placeholders for lists, cards, and titles.
   - `data-state="empty"`: Zero-data state with SVG illustration, helpful explanation, and primary CTA.
   - `data-state="error"`: Network/storage error state with failure message and "Try Again" retry action.
3. **Enforce Safe Area & Hit Targets (Physical Hard Constraints)**:
   - Root container MUST include safe-area declarations:
     - iOS: `data-safe-top="74"` (Dynamic Island clearance ≥71pt), `data-safe-bottom="34"` (Home Bar).
     - Android: `data-safe-top="32"` (Camera punch-hole clearance ≥24dp), `data-safe-bottom="16"`.
   - Every interactive element (button, tab, icon button, input) MUST include:
     `data-hit="44x44"` (for iOS / cross-platform) or `data-hit="48x48"` (for Android).
4. **Interactive Routing & Inspection Bus**:
   - Add `data-nav-target="V-xx"` to clickable elements to enable realistic click-through navigation across all screens.
   - Ensure the template's `postMessage` inspection dispatcher is intact so clicking elements populates the MeaXure property inspector.
5. **Consult Patterns**:
   - Reference `references/component_patterns.md` for pre-built mobile card lists, chip bars, forms, and skeletons.
   - Reference `references/meaxure_attributes.md` for standard data attribute schemas.

---

### Phase 3: Zero-Entropy Verification & Terminal Loop

Run the standalone verification script to test the bundle before finalizing:

```bash
# In any terminal or CLI harness:
python scripts/check_design_bundle.py --workspace . --platform cross_platform
```

Or via platform-specific tool if MCP is available:
- Call `audit_hig_safe_area` (iOS) or `audit_material_spec` (Android).

#### Self-Correction Loop:
- If the validator reports `FAILED`:
  1. Inspect the exact errors (missing states, insufficient safe area in pt/dp, missing tap target sizes, or CDN scripts).
  2. Fix the offending file directly.
  3. Re-run `python scripts/check_design_bundle.py --workspace .` until `Result: PASSED` is printed.
- Once passed, output the Stage 06 Markdown summary report including:
  - 30-Second Executive Review Card.
  - Design Tokens Summary Table.
  - Artboard matrix showing all `V-01~V-xx` screens with their 4 states.
