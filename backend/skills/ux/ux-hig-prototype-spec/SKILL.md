---
name: ux-hig-prototype-spec
description: >-
  Use this skill in Stage 06 (设计实现) to design high-fidelity UI prototypes, enforce iOS Dynamic Island safe areas (>=71pt), and define design tokens.
---

# 高保真 UI 设计实现与安全区防呆技能 (ux-hig-prototype-spec)

## 核心执行步骤
1. **硬件安全区校验**：调用 `audit_hig_safe_area` 确保顶部留白 `>= 71pt`、触控热区 `>= 44pt`。
2. **高保真交互交付**：输出完整设计 Token、状态机（加载/空态/异常）与可预览 HTML 原型规范。
