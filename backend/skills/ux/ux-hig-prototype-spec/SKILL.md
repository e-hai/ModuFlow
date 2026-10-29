---
name: ux-hig-prototype-spec
description: >-
  Use this skill in Stage 06 (设计实现) to design high-fidelity multi-artboard UI prototypes, generate Sketch/Figma-grade interactive HTML inspection bundles with SVG icon & font assets, and enforce iOS Dynamic Island safe areas (>=71pt).
---

# 高保真视觉稿与设计交付包技能 (ux-hig-prototype-spec)

## 核心执行步骤
1. **硬件安全区校验**：调用 `audit_hig_safe_area` 确保顶部留白 `>= 71pt`（推荐 `74pt`）、底部 `>= 34pt`、最小触控热区 `44x44pt`。
2. **真交付：可点开体验的设计交付包**（校验器读画板标注，不读文档自报）：
   - `index.html` 设计工作台（画板/平台/四态切换、标注层、点选检视）、`tokens.json`、`screens/V-xx.html`（每个 PRD 视图一张完整高保真视觉稿，页面可点击跳转）、`assets/icons/*.svg`；
   - 画板约定：`data-device` + `data-safe-top/bottom`、可点击元素 `data-hit="宽x高"`、四态 `data-state`、颜色只用 tokens.json、零外部依赖；
   - 另写一份设计说明文档（拍板摘要卡、Design Tokens 摘要、逐视图四态）。
