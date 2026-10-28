---
name: pm-lean-prd-guard
description: >-
  Use this skill in Stage 03 (产品方向决策) and Stage 05 (产品需求定义) to enforce Lean Startup hypothesis gates in Stage 03, author complete 7+1 Golden Chapter Pure-PM PRD documents with 5-dimension module spec cards and business data dictionaries, strictly avoiding engineering technical leakages (no SQL DDL / JSON Schema), and handle downstream requirement CRs in Stage 05.
---

# 精益方向决策与黄金 7+1 纯业务 PRD 封版技能 (pm-lean-prd-guard)

## 核心执行步骤
1. **工序 03 严禁未验先定**：只输出一页纸 UVP、MoSCoW 减法与 H1~H4 生死假设清单，严禁提前编写代码级 Schema。
2. **工序 05 黄金 7+1 章节纯业务 PRD 规范（严守 PM 业务视角，严禁工程师技术越界）**：
   - **多视角阅读分层设计**：置顶《## 负责人 30 秒拍板摘要卡 (Executive Gate)》，随后展开 7+1 核心章节；
   - **第 0 章**：文档元信息与版本演进履历（版本号、更新时间、变更类型、变更项对照表）；
   - **第一章**：版本定位与范围封版（北极星指标、精简 User Stories、In-Scope P0/P1 vs Out-of-Scope 范围封版矩阵表）；
   - **第二章**：全局信息架构与全站视图索引（Mermaid 页面路由拓扑图、全站视图索引总表 View Index Table `V-01~V-05` 标明视图形态与安全区、主流程泳道图）；
   - **第三章**：功能模块详细规格说明（M1~M6 核心功能全量展开，逐模块必须统一采用五维结构化规格卡：①核心意图导言、②界面布局与组件清单表、③交互流转与计算规则表、④边界条件与异常降级表、⑤模块验收点索引）；
   - **第四章**：商业化特权与付费业务规则（Mermaid StateDiagram 权益状态机、SKU 定价阶梯映射表、免费 vs 付费特权矩阵、付费门槛触发时机、网络超时或未支付时的用户端友好降级体验规则、防刷与风控业务规则）；
   - **第五章**：核心业务数据字典与本地存储策略（纯业务视角，严禁代码/SQL/JSON Schema：①核心业务实体清单与业务关系说明、②逐实体业务数据字典表【字段名、业务含义、业务类型、是否必填、取值范围/枚举值、默认值、校验失败提示文案】、③用户数据存储与隐私分级业务策略【离线持久化诉求、敏感隐私保护诉求、缓存自动清理业务诉求与生命周期】）；
   - **第六章**：全链路数据埋点规范（`E-01~E-12` 核心事件埋点总表、转化漏斗与留存计算公式）；
   - **第七章**：端到端验收用例与体验质量需求（结构化 `AC-01~AC-08` Gherkin 验收矩阵表包含用例ID/场景/Given/When/Then、用户感知级性能要求【如冷启首屏、导出等待感知】、iOS HIG 灵动岛安全区 ≥71pt 与 Apple 4.3 审核合规业务护栏）。
   - **自动化合规校验**：生成交付物后调用 `lint_stage_deliverable` 或运行 `[prd_linter.py](./scripts/prd_linter.py)`。放行线为 100 分。
