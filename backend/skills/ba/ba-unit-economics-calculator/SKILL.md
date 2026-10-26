---
name: ba-unit-economics-calculator
description: >-
  Use this skill in Stage 02 (商业模式分析) to design hybrid monetization ladders (24h Ad-Pass + anti-weekly subscriptions) and calculate LTV, Blended CAC, and payback period.
---

# 变现定价与单位经济精算技能 (ba-unit-economics-calculator)

## 核心执行步骤
1. **单位经济模型精算**：调用专属 MCP 工具 `simulate_unit_economics` 或运行 `[ue_sim.py](./scripts/ue_sim.py)` 校验 `LTV / Blended CAC >= 3.0`。
2. **混合变现护栏设计**：明确免费引流层、`24h Ad-Pass` 激励视频通行证、反周卡年费与终身买断的价格锚点。
