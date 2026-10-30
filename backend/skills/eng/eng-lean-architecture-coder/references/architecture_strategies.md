# Stage 07 Technical Architecture Strategies & Implementation Guide

This reference defines the two official technical strategies supported in Stage 07 (Engineering & Architecture Implementation), along with the 4-layer progressive coding protocol and Gherkin-to-UnitTest mapping patterns.

---

## 1. Standard Minimum Supported Versions Matrix

To maximize global overseas coverage (≥98% active devices) while enabling modern declarative UI, concurrency, and Store submission compliance:

| Platform / Dimension | Minimum Baseline | Target / Compile Baseline | Rationale & Gate Standard |
| :--- | :--- | :--- | :--- |
| **iOS Deployment Target** | **iOS 16.0** | iOS 18.0 | Covers 96%+ active iPhones worldwide; baseline for Compose Multiplatform Skiko Metal rendering & modern SwiftUI lifecycle. |
| **Swift & Xcode** | Swift 5.10 / Xcode 15.0 | Swift 6.0 / Xcode 16.0 | Strict concurrency checks & modern SPM command-line builds. |
| **Android minSdk** | **API 24 (Android 7.0)** | - | Covers 98.5%+ active Android devices globally; Java 8 desugaring & Compose 1.7+ runtime stability. |
| **Android targetSdk / compileSdk** | **API 34 (Android 14)** | API 35 (Android 15) | **Mandatory Google Play submission requirement** (apps targeting < 34 are blocked from store submission). |
| **Java JDK** | **JDK 17 LTS** | JDK 21 LTS | Required baseline by Gradle 8.x and AGP 8.5+ / 9.0. |
| **Kotlin** | **2.0.20** | - | Bundled Compose compiler plugin (Kotlin 2.0+ K2 compiler architecture). |
| **Gradle & AGP** | Gradle 8.9 / AGP 8.5.2 | Gradle 8.10+ / AGP 9.0 | JetBrains official KMP default multi-module structure compatibility. |

---

## 2. Technical Strategy Overview

### Strategy A: `kmp_cmp` (Kotlin & Compose Multiplatform - Default)
Alings with JetBrains official latest KMP Default Structure (AGP 9.0+ compliant).
- **Core Multiplatform Module (`shared/`)**:
  - `src/commonMain/kotlin/com/moduflow/`:
    - `model/`: Data classes representing PRD business dictionary entities.
    - `repository/`: Local offline persistence (Room KMP / SQLite / DataStore).
    - `viewmodel/`: `StateFlow<UiState<T>>` managing 4 states (Ready, Loading, Empty, Error).
    - `theme/`: `Tokens.kt` single source of truth for color, typography, spacing.
    - `components/`: Base UI components enforcing touch target constraints (`48.dp` / `44.dp`).
    - `screens/`: Screen views corresponding to PRD `V-01~V-xx`.
    - `App.kt`: Root composable and navigation host.
  - `src/commonTest/kotlin/com/moduflow/`:
    - Gherkin AC tests covering models and business logic (≥ 80% coverage).
- **Android Host Module (`androidApp/`)**:
  - `com.android.application` packaging.
  - Minimal `MainActivity.kt` calling `App()`.
- **iOS Host Module (`iosApp/`)**:
  - Minimal SwiftUI `iOSApp.swift` hosting `ComposeUIViewController`.

### Strategy B: `dual_native` (Independent Swift & Kotlin)
Used for deep OS-specific capabilities (e.g. Live Activities, Interactive Widgets).
- **iOS (`ios/`)**: Swift 5.10+ / SwiftUI / SPM / SQLite / XCTest.
- **Android (`android/`)**: Kotlin 2.0 / Jetpack Compose / Gradle / Room / JUnit.

---

## 2. 4-Layer Progressive Coding Protocol

### Layer 1: Type & Local Storage Core
- Define data models directly from Stage 05 PRD Data Dictionary tables.
- Implement zero-cloud offline persistence (Room KMP / SQLite).
- Ensure zero external network/cloud dependencies.

### Layer 2: Reactive State & Business Logic
- Model the 4 states:
  ```kotlin
  sealed interface UiState<out T> {
      data object Loading : UiState<Nothing>
      data object Empty : UiState<Nothing>
      data class Error(val message: String, val canRetry: Boolean = true) : UiState<Nothing>
      data class Ready<T>(val data: T) : UiState<T>
  }
  ```
- Implement business calculation rules (e.g., pricing, quota limits, local validation).
- Translate PRD Gherkin `AC-01~AC-08` into automated unit test assertions.

### Layer 3: Design Tokens & Base Components
- Bind `Tokens.kt` / `Tokens.swift` to `tokens.json`.
- Enforce touch target constraints:
  - iOS / Desktop: Minimum 44×44 pt.
  - Android: Minimum 48×48 dp.
- Encapsulate skeleton shimmer animation for `Loading` state.

### Layer 4: Screen Views & Navigation Assembly
- For each PRD view code (`V-01`, `V-02`, etc.):
  - Render all 4 states using `when (state)` (Compose) or `switch state` (SwiftUI).
  - Connect screen transitions according to PRD navigation flows.

---

## 3. Gherkin to Unit Test Translation Pattern

### PRD Gherkin Specification:
```gherkin
Scenario: AC-01 Receipt Auto-Crop Calculates Dimensions
  Given an uncropped image of dimensions 3000x4000
  When the auto-crop edge detector executes
  Then the bounded rectangle area should be between 20% and 95% of the original canvas
```

### Kotlin commonTest Implementation:
```kotlin
package com.moduflow.test

import kotlin.test.Test
import kotlin.test.assertTrue
import com.moduflow.model.CropDetector

class ReceiptProcessingTests {

    @Test
    fun testAC01_AutoCropReceipt_CalculatesCorrectDimensions() {
        // Given
        val detector = CropDetector()
        val originalWidth = 3000
        val originalHeight = 4000

        // When
        val rect = detector.detectCropBounds(originalWidth, originalHeight)
        val originalArea = originalWidth * originalHeight
        val cropArea = rect.width * rect.height
        val ratio = cropArea.toDouble() / originalArea.toDouble()

        // Then
        assertTrue(ratio in 0.20..0.95, "Cropped area ratio $ratio must be between 20% and 95%")
    }
}
```
