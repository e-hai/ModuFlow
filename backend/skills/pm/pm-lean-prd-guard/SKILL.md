---
name: pm-lean-prd-guard
description: >-
  Use this skill in Stage 03 (产品方向决策) and Stage 05 (产品立项与需求定义) to enforce Lean Startup hypothesis gates, prevent premature schema writing in Stage 03, and author complete 7-section Engineering-Grade PRD documents in Stage 05.
---

# 精益方向决策与完整工程级 PRD 封版技能 (pm-lean-prd-guard)

## 核心执行步骤
1. **工序 03 严禁未验先定**：只输出一页纸 UVP、MoSCoW 减法与 H1~H4 生死假设，严禁提前写代码 Schema。
2. **工序 05 反幻觉立项 + 完整 7 大章节工程级 PRD 封版**：
   - **反幻觉铁律**：严禁捏造未录入的实测花费与转化数据（未录入时必须显式标注 `[待回填实测值 | 目标基准: xxx]`）；
   - **完整 PRD 7 大章节（严禁缩水为简表）**：①立项评估与 MVP 范围封版（In-Scope vs Out-of-Scope）；②全局信息架构 (IA) 与核心状态流转图 (Mermaid)；③逐模块、逐页面详细功能需求规格（M1~M6 页面区域、UI 元素、手势/阈值公式、异常降级）；④完整数据字典与云端/本地接口契约（JSON Schema、SQLite 表结构、Keychain、Remote Config）；⑤商业化计费与权限状态机；⑥全链路数据埋点字典 (Tracking Plan)；⑦非功能性需求与全量 Gherkin 验收标准 (AC-01~AC-08+)。
   - 生成后调用 `lint_stage_deliverable` 或运行 `[prd_linter.py](./scripts/prd_linter.py)` 校验合规性。
