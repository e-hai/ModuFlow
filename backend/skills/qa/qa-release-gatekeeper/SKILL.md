---
name: qa-release-gatekeeper
description: >-
  Use this skill in Stage 08 (测试与 QA) and Stage 09 (发布与上线) to execute Gherkin E2E test matrices, enforce P0/P1 bug gates, and audit App Store 4.3 compliance.
---

# 质量门禁与提审合规审查技能 (qa-release-gatekeeper)

## 核心执行步骤
1. **提审合规与阻断门禁检查**：调用 `audit_app_store_compliance` 确认具备 Remote Config 降级保护开关且 P0/P1 未决缺陷清零。
2. **端到端验收矩阵**：逐条核验工序 05 冻结的 Gherkin 验收标准与弱网/低端机表现。
