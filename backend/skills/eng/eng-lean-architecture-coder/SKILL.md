---
name: eng-lean-architecture-coder
description: >-
  Universal Stage 07 (Engineering Implementation) skill for any AI agent harness (Claude Code CLI, Antigravity, Cursor, ModuFlow Runner). Enforces tech-stack contract first, supports KMP/CMP (JetBrains new default structure - default) and Dual-Native architectures, zero client-side AI inference cost, and 80%+ unit test coverage gates.
---

# Universal Engineering Architecture & Coding Specification (eng-lean-architecture-coder)

This skill guides an AI agent harness (Claude Code CLI, Antigravity/`agy`, Cursor, or ModuFlow daemon) to architect, generate, and verify **production-grade mobile client code** based on upstream PRD specifications (Stage 05) and Canonical Design Bundles (Stage 06).

---

## Technical Strategy Selection

ModuFlow supports two official mobile architecture strategies, controlled by `tech_stack.json` and project profile:
1. **Strategy A (Default): `kmp_cmp` (Kotlin & Compose Multiplatform)**
   - Aligns with JetBrains official latest New KMP Default Structure (AGP 9.0+ compliant).
   - Multiplatform library module (`shared/`) holds 100% shared models, SQLite/Room persistence, ViewModels, and Compose UI.
   - Standalone application packaging modules: `androidApp/` (com.android.application) and `iosApp/` (SwiftUI host wrapper).
   - Single source of truth for logic and tests, cutting AI token overhead by ~50%.
2. **Strategy B: `dual_native` (Independent Swift & Kotlin)**
   - iOS native package (`ios/` with SwiftUI + SPM).
   - Android native app (`android/` with Jetpack Compose + Gradle).
   - Recommended only when deeply integrating iOS/Android-exclusive hardware or system widgets.

---

## 3-Phase Progressive Engineering Protocol

### Phase 1: Tech Stack Contract & Scaffolding Initialization

1. **Lock Tech Stack Contract & Compatibility Baselines**:
   Read `authorization.yaml` profile.
   Ensure `tech_stack.json` strictly satisfies the minimum supported versions baseline:
   - **iOS Deployment Target**: `min_deployment_target: "16.0"` (covers ≥96% global active iPhones).
   - **Android minSdk**: `min_sdk: 24` (Android 7.0, covers ≥98.5% global active devices).
   - **Android targetSdk**: `target_sdk: 34` (Android 14, **mandatory Google Play Store requirement**).
   - **Toolchain**: JDK 17, Kotlin 2.0+, Gradle 8.9+, Compose Multiplatform 1.7.0.
   Copy the appropriate tech stack template to `./tech_stack.json`:
   - For `kmp_cmp` (default): copy `templates/kmp_cmp/tech_stack.template.json`.
   - For `dual_native`: copy `templates/dual_native/tech_stack.template.json`.
2. **Initialize Scaffold**:
   - For KMP/CMP: Copy `templates/kmp_cmp/` files to root:
     - `gradle/libs.versions.toml`
     - `build.gradle.kts` & `settings.gradle.kts`
     - `shared/build.gradle.kts`
     - `androidApp/` and `iosApp/` minimal host entrypoints
   - For Dual-Native: Copy `templates/dual_native/` files to `ios/` and `android/`.
3. **Map Design Tokens**:
   Copy `Tokens.kt.template` (or `Tokens.swift.template`) to the design system module.
   Verify all colors and metrics match `tokens.json`.

---

### Phase 2: Progressive 4-Layer Implementation

Harness MUST execute implementation in 4 distinct layers:

#### Layer 1: Type & Local Storage Core
- Convert Stage 05 PRD Data Dictionary tables into Kotlin Data Classes / Swift Structs.
- Implement offline-first local persistence (Room KMP / SQLite / DataStore).
- **Rule**: Absolutely zero cloud AI / external API dependencies for offline functionality.

#### Layer 2: Reactive State Machine & Business Logic
- Implement `UiState<T>` managing 4 states: `Ready(data)`, `Loading`, `Empty`, `Error(message)`.
- Implement ViewModel handling state flows and business calculation rules.
- Translate Stage 05 PRD Gherkin scenarios (`AC-01~AC-08`) into automated unit tests.
- **Rule**: Unit test line coverage on models and business logic must reach **≥ 80%**.

#### Layer 3: Tokens & Base Components
- Expose `MfTokens` singleton for colors, typography, and safe area metrics.
- Implement base buttons and touch targets enforcing physical minimums:
  - Material 3 (Android / Compose): `48.dp` minimum touch target.
  - Apple HIG (iOS / Compose iOS): `44.dp` / `44.pt` minimum touch target.
- Implement skeleton pulse shimmer component for `Loading` state.

#### Layer 4: Screen Views & Routing Assembly
- For each PRD view (`V-01~V-xx`), implement the corresponding Compose Screen / SwiftUI View.
- Implement full 4-state rendering using `when (uiState)` or `switch uiState`.
- Wire navigation transitions corresponding to `data-nav-target` in Stage 06 design artboards.

---

### Phase 3: Zero-Entropy Verification & Terminal Loop

Run the standalone verification script to test the deliverable before finalizing:

```bash
# In any terminal or CLI harness:
python scripts/check_eng_deliverable.py --workspace .
```

#### Self-Correction Loop:
1. If the validator reports `FAILED`:
   - Inspect specific errors (missing modules, missing test files, unauthorized AI SDK imports, missing 4-state branches).
   - Fix the offending files.
   - Re-run `python scripts/check_eng_deliverable.py --workspace .` until `Result: PASSED` is printed.
2. Run unit tests (`./gradlew check` or `swift test`) to verify test suite passes green.
3. Once passed, output the Stage 07 Markdown deliverable report including:
   - 30-Second Executive Review Card.
   - Architecture & Tech Stack Summary Table.
   - Core Unit Test Coverage Matrix (Module, Test File, Coverage %, Status).
