---
name: ux-hig-prototype-spec
description: >-
  Use this skill in Stage 06 (设计实现) to design high-fidelity multi-artboard UI prototypes, generate Sketch/Figma-grade interactive HTML inspection bundles with SVG icon & font assets, and enforce iOS Dynamic Island safe areas (>=71pt).
---

# 高保真 UI 设计实现与 Sketch 级标注包交付技能 (ux-hig-prototype-spec)

## 核心执行步骤
1. **硬件安全区校验**：调用 `audit_hig_safe_area` 确保顶部留白 `>= 71pt`（推荐 `74pt`）、底部 `>= 34pt`、最小触控热区 `44x44pt`。
2. **双轨真交付（Markdown 设计规范 + Sketch 级 HTML 标注工作台与资产包）**：
   - 输出完整 Markdown 设计规范文档（含 SwiftUI Design Tokens 代码契约与 V-01~V-05 图层树）；
   - 在工作区同步生成 `index.html`（覆盖全部 PRD 核心视图 V-01~V-05 画板切换、点选组件检视尺寸/间距/色号并一键复制 SwiftUI 与 Tailwind 代码、安全区标尺开关）以及 `assets/icons/*.svg`、`assets/fonts/`、`assets/tokens/design_tokens.json` 与全量打包 `.zip`。
