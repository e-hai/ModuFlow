---
name: pm-lean-prd-guard
description: >-
  Use this skill in Stage 03 (产品方向决策) and Stage 04 (产品需求定义) to enforce Lean Startup hypothesis gates in Stage 03, author complete 7+1 Golden Chapter Pure-PM PRD documents with 5-dimension module spec cards and business data dictionaries, strictly avoiding engineering technical leakages (no SQL DDL / JSON Schema), and handle downstream requirement CRs in Stage 04.
---

# 精益方向决策与黄金 7+1 纯业务 PRD 封版技能 (pm-lean-prd-guard)

## 核心执行步骤
1. **工序 03 严禁未验先定**：只输出一页纸 UVP、MoSCoW 减法与 H1~H4 生死假设清单，严禁提前编写代码级 Schema。
2. **工序 04 黄金 7+1 章节纯业务 PRD 规范（严守 PM 业务视角，严禁工程师技术越界）**：
   - **多视角阅读分层设计**：置顶《## 负责人 30 秒拍板摘要卡 (Executive Gate)》，随后展开 7+1 核心章节；
   - **第 0 章**：版本表固定四列「上线版本、稿次、来源、变更」。上线版本是给用户看的三段号，如 `1.0.0`。稿次只能是 `r` 加整数，如 `r1`、`r2`，同一上线版本里工序之间改稿只加稿次，禁止写成 `1.0.1`。首版来源写「工序 03」；其后每一行来源写变更单，或「承接 1.0.0 需求 r4」这种上一轮上线版本加稿次。旧稿不改，只追加一行。
   - **第一章**：版本定位与范围封版（北极星指标、精简 User Stories、In-Scope P0/P1 vs Out-of-Scope 范围封版矩阵表）；
   - **第二章**：全局信息架构与全站视图索引。视图索引用表格，每行一个页面：`id` 是小写英文短名（如 `home`），用来命名 `screens/{id}.html`，也用于跳转；`name` 只解释这一页（如「首页」），不参与路径。同一份清单里 `id` 不能重复。验收编号 `AC-xx` 和埋点编号 `E-xx` 仍用编号。
   - **第三章**：功能模块详细规格说明（M1~M6 核心功能全量展开，逐模块必须统一采用五维结构化规格卡：①核心意图导言、②界面布局与组件清单表、③交互流转与计算规则表、④边界条件与异常降级表、⑤模块验收点索引）；
   - **第四章**：商业化特权与付费业务规则（Mermaid StateDiagram 权益状态机、SKU 定价阶梯映射表、免费 vs 付费特权矩阵、付费门槛触发时机、网络超时或未支付时的用户端友好降级体验规则、防刷与风控业务规则）；
   - **第五章**：核心业务数据字典与本地存储策略（纯业务视角，严禁代码/SQL/JSON Schema：①核心业务实体清单与业务关系说明、②逐实体业务数据字典表【字段名、业务含义、业务类型、是否必填、取值范围/枚举值、默认值、校验失败提示文案】、③用户数据存储与隐私分级业务策略【离线持久化诉求、敏感隐私保护诉求、缓存自动清理业务诉求与生命周期】）；
   - **第六章**：全链路数据埋点规范（`E-01~E-12` 核心事件埋点总表、转化漏斗与留存计算公式）；
   - **第七章**：端到端验收用例与体验质量需求（结构化 `AC-01~AC-08` Gherkin 验收矩阵表包含用例ID/场景/Given/When/Then、用户感知级性能要求【如冷启首屏、导出等待感知】、iOS HIG 灵动岛安全区 ≥71pt 与 Apple 4.3 审核合规业务护栏）。清单里每条验收写 id、view_id、given、when、then，view_id 用视图索引里的 id。
   - **自动化合规校验**：生成交付物后调用 `lint_stage_deliverable` 或运行 `[prd_linter.py](./scripts/prd_linter.py)`。放行线为 100 分。
