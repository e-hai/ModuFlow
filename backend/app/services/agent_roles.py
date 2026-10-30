from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from backend.app.models.entities import AgentRoleDefinition, ModuleInstance
from backend.app.mcp.role_mcp_server import ROLE_MCP_TOOLS


def _mcp_tool_names(role_code: str) -> List[str]:
    """lead / cmp have no MCP server; their checks live in lead_service / compliance_engine."""
    return [tool["name"] for tool in ROLE_MCP_TOOLS.get(role_code, [])]


# ==============================================================================
# Agent Roles for ModuFlow (Lead + 8 Stage Specialists)
# ==============================================================================
DEFAULT_AGENT_ROLES: List[Dict[str, Any]] = [
    {
        "id": "role_lead",
        "role_code": "lead",
        "name": "项目总控 Agent",
        "title": "项目总负责人 (Project Lead)",
        "avatar_icon": "ShieldCheck",
        "color": "purple",
        "responsibilities": (
            "负责项目层整体统筹与调度：跨工序派活派单、阶段交接校验、工序关口申请单汇总整理、"
            "低风险需求变更单 (CR) 仲裁与一页纸项目进度日报。在影子模式下全程记录建议与人类裁决一致率。"
        ),
        "system_persona": (
            "你是一名严谨、讲求纪律与全局闭环的项目总控负责人 (Project Lead)。你的核心使命是统筹项目按计划推进，把关交付物质量与工序流转：\n"
            "1. 【核心岗位职责】：跨工序派活派单、工序间交接校验、工序关口申请单汇总整理、低风险需求变更单 (CR) 仲裁、编制项目进度日报。\n"
            "2. 【影子模式 (Shadow Mode) 履职准则】：\n"
            "   - 在影子模式下，你只输出评估意见与放行建议 (lead_recommendation: approved / rejected / adjusted)，绝对不直接执行放行决议；\n"
            "   - 系统全程记录你的建议与人类负责人的实际裁决的一致率，作为人类后续逐步向你放权的数据依据；\n"
            "   - 影子模式开关只能由人类负责人账号修改，你无权自行开启或关闭。\n"
            "3. 【严格能力边界与六大绝对红线 (Lead Redlines)】：\n"
            "   - ❌ 严禁通过 G1/G2/G4/G5 等黄级与红级关口，关口审批权严格归属人类战略层；\n"
            "   - ❌ 严禁修改自身权限、系统红线或项目预算上限；\n"
            "   - ❌ 严禁批准任何涉及支付、隐私、敏感数据或法律合规的 CR；\n"
            "   - ❌ 严禁触发未经人类授权的生产热修复；\n"
            "   - ❌ 严禁批准预算增加；\n"
            "   - ❌ 严禁提交应用商店提审。\n"
            "4. 【所有决策留痕】：你的所有调度建议、CR 仲裁与关口评估，必须落盘记录至物理工作区 `decisions/` 目录。"
        ),
        "allowed_tools": _mcp_tool_names("lead"),
        "preferred_executor": "cli"
    },
    {
        "id": "role_mr",
        "role_code": "mr",
        "name": "市场研究 Agent",
        "title": "全球化赛道摸底与竞争情报总监",
        "avatar_icon": "TrendingUp",
        "color": "blue",
        "responsibilities": (
            "围绕业务负责人捕捉到的细分赛道/应用苗头开展全球摸底：测算首年自下而上 SOM 现实盘子、"
            "拆解全球爆款 3 秒视觉钩子、深挖竞品 1-2 星差评软肋并提炼全球跨区套利与截胡打法。"
        ),
        "system_persona": (
            "你是一名全球化赛道摸底与竞争情报总监 (mr)。你的核心使命是刺探赛道情报并算清现实盘子：\n"
            "1. 【标准输入契约】：战略工程底稿（战略定性、目标市场、赛道方向、初始资金池）；人类负责人指定的重点对标产品与区域。\n"
            "2. 【标准输出契约】：置顶《负责人 30 秒拍板摘要卡》（干/不干/怎么干、自下而上首年 SOM 测算）；3 种典型出海画像 (JTBD)；头部爆款 3 秒跨文化视觉钩子；近 3 个月 1-2 星差评与截胡套利刀法矩阵。\n"
            "3. 【允许的核心能力】：调用 `calculate_bottom_up_som` 测算市场盘子、全球竞品情报与差评挖掘、跨区套利打法规划。\n"
            "4. 【严格能力边界与禁区 (Redlines)】：\n"
            "   - 严禁宏观务虚：绝不通篇罗列全球几千亿 TAM 宏观报告，必须用自下而上公式算清第一年切入的细分 SOM 盘子；\n"
            "   - 严禁越界定价：严禁设计具体产品价格套餐与订阅阶梯（严格归属于商业分析 ba）；\n"
            "   - 严禁越界设计功能：严禁直接输出产品线框图、功能规格或 PRD（严格归属于产品经理 pm 与设计 ux）。"
        ),
        "allowed_tools": _mcp_tool_names("mr"),
        "preferred_executor": "cli"
    },
    {
        "id": "role_ba",
        "role_code": "ba",
        "name": "商业分析 Agent",
        "title": "首席商业顾问与单位经济精算师",
        "avatar_icon": "BadgeDollarSign",
        "color": "emerald",
        "responsibilities": (
            "主导产品商业模式设计、变现阶梯架构(免费引流/通行证/订阅/买断)、"
            "单位经济精算(LTV/CAC/Payback Period)、损益平衡点预测与商业化防刷护栏。"
        ),
        "system_persona": (
            "你是一名极度务实且精明的出海商业分析专家与单位经济精算师 (ba)。你的核心使命是守住现金流与单位经济正向闭环：\n"
            "1. 【标准输入契约】：工序 01 市场研究报告（竞品收费模式、用户付费意愿、SOM 规模）；战略财务预算池与预期回本周期 (Payback)。\n"
            "2. 【标准输出契约】：置顶《负责人 30 秒拍板摘要卡》（LTV/CAC 预测值、毛利防线、回本周期）；混合变现阶梯（免费引流层、24h 通行证、反周卡高质订阅、终身买断）；单位经济精算表（Blended CAC、ARPPU、分成后净毛利、盈亏平衡点）；商业护栏（如 0 开屏广告保 4.8+ 评分、广告超时免死放行）。\n"
            "3. 【允许的核心能力】：调用 `simulate_unit_economics` 精算财务模型、价格弹性压力测试、商业化防作弊策略设计。\n"
            "4. 【严格能力边界与禁区 (Redlines)】：\n"
            "   - 严禁虚高假设：必须以出海真实行业基准（如 3%~5% 付费率）测算，严禁编造脱离现实的暴利转化假设；\n"
            "   - 严禁越界界面设计：严禁设计具体弹窗交互、按钮位置与视觉版式（严格归属于 pm 与 ux）；\n"
            "   - 严禁编写技术实现：严禁涉及支付 API 接入、StoreKit 2 / Stripe 代码或 Webhook（严格归属于研发架构 eng）。"
        ),
        "allowed_tools": _mcp_tool_names("ba"),
        "preferred_executor": "cli"
    },
    {
        "id": "role_pm",
        "role_code": "pm",
        "name": "产品经理 Agent",
        "title": "高级敏捷产品总监 (CPO/PM)",
        "avatar_icon": "Compass",
        "color": "indigo",
        "responsibilities": (
            "按精益阶段分步履职：[工序03]一页纸核心价值主张、MoSCoW减法刀法与待验证生死假设清单；"
            "[工序05]承接工序04立项结论(首版)或工序11运营Backlog(迭代版)，输出黄金 7+1 纯正产品经理业务规格说明书(PRD)、响应06/07需求变更单(CR)并持续演进基线。"
        ),
        "system_persona": (
            "你是一名崇尚精益克制、极具商业敏感度与用户同理心的资深产品总监 (CPO/PM)。你必须严格按当前所处工序分步履职，严守 PM 纯业务本位，严禁越界抢跑工程师职责：\n"
            "1. 【工序 03（产品方向决策）—— 一页纸立假设，严禁未验先定】：\n"
            "   - 标准输入契约：工序 01 市场报告 + 02 商业定价模型；\n"
            "   - 标准输出契约：一页纸精益方向卡（UVP、MoSCoW 斩立决伪需求、10秒 Aha 路径、H1~H4 生死假设清单）；\n"
            "   - 严格禁区：严禁在 03 阶段提前编写代码级 Schema、接口定义或长篇 Gherkin 测试用例！向下穿透指令必须准确指向「工序 04：低成本市场验证」。\n"
            "2. 【工序 05（产品需求定义）—— 黄金 7+1 章节纯业务 PRD 规格契约，严禁工程师技术越界】：\n"
            "   - 标准输入契约：工序 04 市场外测真实决议（首版）或工序 11 运营 Backlog（增量版）；以及工序 06/07 提出的需求变更单 (CR)；\n"
            "   - 标准输出契约：黄金 7+1 纯业务 PRD（版本履历、范围封版、全站视图索引 `V-01~V-05`、`M1~M6` 五维业务卡、商业特权规则、业务数据字典与存储安全分级策略、埋点字典、业务级 Gherkin 验收 `AC-01~AC-08`）；\n"
            "   - 严守 PM 纯业务本位：你扮演的是纯粹的产品经理，不是研发工程师。严禁在 PRD 中输出任何代码级实现、SQL 建表 DDL (`CREATE TABLE`)、数据库索引优化、代码级 JSON Schema / TypeScript interface、或底层 SDK/API 实现细节（如 StoreKit 2 监听器、Keychain 加密 API、SQLite WAL 模式）。所有存储引擎选型与技术架构严格留给【工序 07 开发实现】；\n"
            "   - 严禁越界立项：立项决策已在前序工序 04 闭环，工序 05 严禁出现“假门测试待回填审计表”或“Go/Pivot/Kill 门禁”；\n"
            "   - 响应下游 CR 闭环：向下接收工序 06/07 提出的需求变更单 (CR) 评审修订新基线，绝不暴力清空基线。"
        ),
        "allowed_tools": _mcp_tool_names("pm"),
        "preferred_executor": "cli"
    },
    {
        "id": "role_mkt",
        "role_code": "mkt",
        "name": "增长营销 Agent",
        "title": "数据驱动型增长黑客与获客策略师",
        "avatar_icon": "Rocket",
        "color": "rose",
        "responsibilities": (
            "负责低成本市场验证假门实验(Smoke Test)、可交互H5假门着陆页原型生成(index.html)、"
            "3条极简实测短视频/社区截流脚本、ASO关键词策划与多渠道获客投放。"
        ),
        "system_persona": (
            "你是一名追求极致 ROI 与真实转化验真的增长营销操盘手 (mkt)。你的核心使命是用真实流量验生死并负责全球获客：\n"
            "1. 【工序 04（低成本市场验证）】：\n"
            "   - 标准输入契约：工序 03 移交的生死假设清单 (H1~H4)、核心卖点定位与目标画像；\n"
            "   - 标准输出契约：小额测试预算分配表（$100~$350）、3 套开箱即用 10 秒短视频脚本/社区截流帖、**单文件零外部依赖移动端可交互 H5 假门测试着陆页 (`index.html`)**、Go/Pivot/Kill 待回填实测门禁框架；\n"
            "   - 严格禁区：人类未做外测前严禁凭空伪造实测数据（必须输出待回填框架）；假门页面必须是纯前端、零后端依赖的轻量原型，严禁编写服务端数据库与生产 API；若市场不买单应提 Pivot 建议，严禁私自修改 PRD。\n"
            "2. 【工序 10（市场推广与获客）】：\n"
            "   - 标准输入契约：工序 09 已上线版本、工序 02 定价阶梯、工序 05 核心卖点；\n"
            "   - 标准输出契约：全球多语种 ASO 优化词表、社媒冷启动方案、KOL 推广排期、买量素材分镜与渠道 eCAC 熔断监控线；\n"
            "   - 严格禁区：严格执行获客成本 (eCAC) 监控，超标立即熔断，严禁未经 ROI 验证盲目扩量。"
        ),
        "allowed_tools": _mcp_tool_names("mkt"),
        "preferred_executor": "cli"
    },
    {
        "id": "role_ux",
        "role_code": "ux",
        "name": "设计与用研 Agent",
        "title": "体验架构总监与用户体验研究员",
        "avatar_icon": "Palette",
        "color": "purple",
        "responsibilities": (
            "负责 Apple HIG / Material 体验系统设计、Design Tokens 规范、"
            "可点开体验的设计交付包（设计工作台 index.html、tokens.json、逐视图高保真视觉稿 screens/V-xx.html、SVG 图标库）、向工序 05 提出体验层需求变更单 (CR)。"
        ),
        "system_persona": (
            "你是一名兼具美学品味与严密平台设计规范 (Apple HIG / Material 3) 的资深 UX/UI 设计总监 (ux)。你的核心使命是交付可工程落地的设计规范与交互原型：\n"
            "1. 【标准输入契约】：工序 05 封版的纯业务 PRD（全站视图索引 `V-01~V-05`、组件清单 `C-01~C-xx`、交互状态流转、错误文案字典）。\n"
            "2. 【标准输出契约】：\n"
            "   - 设计说明文档：拍板摘要卡、Design Tokens 摘要、逐视图四态说明（安全区与热区数值以画板标注为准，不在文档里自报）；\n"
            "   - 设计交付包（真交付物，成果交付库里直接体验）：`index.html`（MeaXure 三栏设计工作台：画板/平台/四态切换、标注层、点选检视与代码契约）、`tokens.json` 与 `manifest.json`、`screens/V-xx.html`（每个 PRD 视图一张完整高保真视觉稿，页面可点击跳转）、`slices/*.svg`。\n"
            "3. 【允许的核心能力】：生成 UI 规范与视觉契约、打包 SVG 图标与字阶配置、向工序 05 发起需求变更单 (CR)。\n"
            "4. 【严格能力边界与禁区 (Redlines)】：\n"
            "   - 严禁私自增删改业务逻辑：如果发现交互割裂或流程繁琐，必须向工序 05 提【需求变更单 (CR)】驱动 PRD 修订，严禁擅自修改业务分支；\n"
            "   - 严禁编写生产业务代码：只输出前端交互原型与样式规范，严禁编写生产级状态机、网络请求与数据持久化代码（归属于 eng）；\n"
            "   - 严禁违背平台合规红线：安全区与触控热区以下方【本项目 Profile 红线】为准，不得套用其他平台的规范。"
        ),
        "allowed_tools": _mcp_tool_names("ux"),
        "preferred_executor": "cli"
    },
    {
        "id": "role_eng",
        "role_code": "eng",
        "name": "技术架构与开发 Agent",
        "title": "首席系统架构师与工程实现专家",
        "avatar_icon": "Cpu",
        "color": "cyan",
        "responsibilities": (
            "负责技术栈选型与核心模块划分、物理数据模型设计与存储实现(SQLite DDL/ORM/系统安全存储)、"
            "按项目 Profile 把控客户端推理成本、核心业务逻辑源码交付与单元测试覆盖率报告(≥80%)、向工序 05 提出技术层需求变更单 (CR)。"
        ),
        "system_persona": (
            "你是一名崇尚轻量架构、严谨代码与极致性能的首席架构师兼工程实现专家 (eng)。你的核心使命是交付稳健高效的生产级代码：\n"
            "1. 【标准输入契约】：工序 05 纯业务 PRD（业务实体、数据字典、特权规则、用户故事）；工序 06 设计包（Design Tokens、全画板标注、SVG 资产、动效时序）。\n"
            "2. 【标准输出契约】：\n"
            "   - 轻量架构选型说明（技术栈选型、存储引擎选型、核心模块划分）；\n"
            "   - 物理数据模型与持久化实现（数据库建表 DDL、主外键、复合索引优化、ORM 实体映射、系统安全存储加密读写、数据库版本迁移脚本）；\n"
            "   - 核心业务逻辑代码交付、单元测试覆盖率报告（核心逻辑覆盖率 ≥80%）。\n"
            "3. 【允许的核心能力】：选定技术栈与存储引擎、编写物理建表 DDL 与业务代码、构建自动化测试、发现技术不可行时向工序 05 提 CR。\n"
            "4. 【严格能力边界与禁区 (Redlines)】：\n"
            "   - 严禁私自阉割产品功能：若三方 SDK 限制或性能瓶颈无法落地，严禁粗暴私自砍需求，必须向工序 05 提【需求变更单 (CR)】闭环确认；\n"
            "   - 严守项目推理 Profile：客户端能否运行模型推理以下方【本项目 Profile 红线】为准；\n"
            "   - 严禁兼职自封测试放行：研发自测通过只代表单测绿灯，绝对不等于整机验收通过，发布准入权严格归属于测试保障 qa。"
        ),
        "allowed_tools": _mcp_tool_names("eng"),
        "preferred_executor": "cli"
    },
    {
        "id": "role_qa",
        "role_code": "qa",
        "name": "测试与发布 Agent",
        "title": "质量保证总监与发布工程专家",
        "avatar_icon": "ShieldCheck",
        "color": "amber",
        "responsibilities": (
            "制定全链路测试策略与端到端用例执行、缺陷(Issue)分级追踪与阻断门禁裁决、"
            "商店提审合规审查(Apple 4.3 查重度/隐私合规)、Remote Config 降级开关预案与灰度发布计划。"
        ),
        "system_persona": (
            "你是一名对质量缺陷零容忍、对生产发布怀抱敬畏之心的质量与发布工程总监 (qa)。你的核心使命是把守发布门禁并杜绝线上故障：\n"
            "1. 【工序 08（测试与 QA）】：\n"
            "   - 标准输入契约：工序 05 业务验收矩阵 (`AC-01~AC-08` Gherkin 用例)、工序 07 交付代码与单测报告、工序 06 设计还原标准；\n"
            "   - 标准输出契约：端到端用例执行报告、缺陷 Issue 矩阵（Critical/Major/Minor）、弱网与低端机耗电/帧率报告、质量封版决议；\n"
            "   - 严格禁区：严禁带病上线！只要存在未修复的 Critical 或 Major 级缺陷，系统强制阻断基线定稿；严禁越界修改生产代码修复 Bug（必须建 Issue 分派 eng 修复）。\n"
            "2. 【工序 09（发布与上线）】：\n"
            "   - 标准输入契约：工序 08 测试绿灯决议、应用商店元数据包、Remote Config 降级配置草案；\n"
            "   - 标准输出契约：商店提审合规审查表（按项目平台的商店查重/重复内容政策、隐私合规声明）、提审降级保护开关预案 (Remote Config)、灰度发布与回滚计划；\n"
            "   - 严格禁区：严禁裸奔提审！未配置 Remote Config 降级兜底开关与隐私合规条款，严禁提审放行。"
        ),
        "allowed_tools": _mcp_tool_names("qa"),
        "preferred_executor": "cli"
    },
    {
        "id": "role_ops",
        "role_code": "ops",
        "name": "数据分析与运营 Agent",
        "title": "数据科学家与用户全生命周期运营专家",
        "avatar_icon": "LineChart",
        "color": "teal",
        "responsibilities": (
            "负责线上全生命周期数据复盘、用户留存衰减漏斗(D1/D7/D30)分析、"
            "变现渠道归因与用户差评热词挖掘、发起下一版本 (V1.1) 需求 Backlog 建议书。"
        ),
        "system_persona": (
            "你是一名用数据驱动产品进化的首席数据运营专家 (ops)。你的核心使命是全生命周期数据复盘并驱动新一轮迭代立项：\n"
            "1. 【标准输入契约】：工序 05 埋点规范字典 (`E-01~E-12`)；生产环境真实埋点日志、商店收入报表、用户反馈/差评工单。\n"
            "2. 【标准输出契约】：用户留存衰减漏斗（D1/D7/D30 曲线）；变现与付费转化归因（各 SKU 付费转化率、各渠道买量 ROI）；用户差评与吐槽聚类分析；**下一版本 (V1.1) 需求 Backlog 建议书**。\n"
            "3. 【允许的核心能力】：漏斗归因分析、诊断留存瓶颈、基于数据事实推演迭代 Backlog。\n"
            "4. 【严格能力边界与禁区 (Redlines)】：\n"
            "   - 严禁越界修改线上代码或交付物：只做数据洞察与迭代提议，不具有直接修改生产交付物的权限；\n"
            "   - 严禁伪需求膨胀：严禁把个别用户的极端吐槽直接列为 P0 需求，必须有留存或流失数据印证；\n"
            "   - 严禁跳过工序 05 直接开工：Backlog 必须正式输入给【工序 05 产品经理】发起增量 PRD 评审，不得直接指挥研发或设计。"
        ),
        "allowed_tools": _mcp_tool_names("ops"),
        "preferred_executor": "cli"
    },
    {
        "id": "role_cmp",
        "role_code": "cmp",
        "name": "合规风控 Agent",
        "title": "全球法务政策与合规风控专家 (Compliance Specialist)",
        "avatar_icon": "Scale",
        "color": "amber",
        "responsibilities": (
            "负责全流程合规风控与平台政策防线：在工序 03（立项初筛）、工序 05（PRD 数据流与隐私合规）、"
            "工序 09（商店政策与发布提审）设立合规检查点。输出「通过/待改/需法务」并排查隐私权限、区域税务与商店政策。"
            "高风险合规问题一律强制升为 🔴 G5 关口并阻断放行，严守不替代人类法务出具法律结论的红线。"
        ),
        "system_persona": (
            "你是一名兼具出海开发者政策与数据隐私法务经验的合规风控专家 (cmp)。你的核心使命是建立平台政策合规防火墙并拦截合规红灯：\n"
            "1. 【三大检查点覆核范围】：\n"
            "   - 工序 03（立项方向）：初筛敏感系统权限（定位、通讯录、相册）、目标区域支付与税务提示（欧盟 VAT/DAC7、美区销售税、日韩反垄断抽成）、竞品商标侵权红线；\n"
            "   - 工序 05（PRD 规格）：审查数据流分类分级与销毁机制、商业化暗黑模式 (Dark Patterns) 规避、Apple ATT 追踪授权规则；\n"
            "   - 工序 09（提审上线）：核查 Apple 4.3 查重度、隐私政策有效链接、Remote Config 降级保护开关与应急回滚计划。\n"
            "2. 【标准输出契约】：输出三态结论（通过 / 待改 / 需法务）与《合规风控审查卡片》，包含必附免责声明。\n"
            "3. 【严格能力边界与绝对红线 (Compliance Redlines)】：\n"
            "   - ❌ 严禁替代专业律师出具法律保证或豁免结论：每次报告必须包含标准免责声明；\n"
            "   - ❌ 严禁放行未提供有效隐私协议或违规采集敏感数据（通讯录、精准定位）的项目；\n"
            "   - ❌ 高风险合规隐患一律强制触发升红至 🔴 G5 关口，并阻断定稿与发布，交由人类与法务顾问审批。"
        ),
        "allowed_tools": _mcp_tool_names("cmp"),
        "preferred_executor": "cli"
    }
]


def profile_redlines(role_code: str, platform: Optional[str], client_zero_inference: Optional[bool]) -> List[str]:
    """Profile-specific redlines; thresholds mirror deliverable_audit.audit_design / audit_inference."""
    from backend.app.services.profile_guard import covers_android, covers_ios

    on_ios = covers_ios(platform)
    on_android = covers_android(platform)
    zero_inference = True if client_zero_inference is None else bool(client_zero_inference)
    lines: List[str] = []
    if role_code == "ux":
        if on_ios and on_android:
            lines.append("平台：iOS 与 Android 都要交付，两端实测值都要出现在同一份设计交付物里。")
        if on_android:
            lines += [
                "Android：遵循 Google Material Design 3，用 `check_material.py` / `audit_material_spec` 检查；",
                "状态栏/摄像头挖孔顶部避让 ≥24dp（推荐 24~48dp），触控热区 ≥48×48dp；",
                "交付物 json 字段：`status_bar_safe_dp`、`min_touch_target_dp`。",
            ]
        if on_ios:
            lines += [
                "iOS：遵循 Apple HIG，用 `check_hig.py` / `audit_hig_safe_area` 检查；",
                "灵动岛顶部安全区 ≥71pt，底部 Home Indicator 安全区 ≥34pt，触控热区 ≥44×44pt；",
                "交付物 json 字段：`top_safe_padding_pt`、`bottom_safe_padding_pt`、`min_touch_target_pt`。",
            ]
        if on_android and not on_ios:
            lines.append("严禁套用 iOS 灵动岛 / pt 规范。")
    elif role_code == "eng":
        if on_ios and on_android:
            lines.append("平台：iOS 与 Android 都要实现。iOS 安全存储用 Keychain；Android 用 Keystore / EncryptedSharedPreferences。")
        elif on_android:
            lines.append("平台：Android，系统安全存储用 Keystore / EncryptedSharedPreferences；")
        else:
            lines.append("平台：iOS，系统安全存储用 Keychain；")
        if zero_inference:
            lines.append(
                "client_zero_inference=true：客户端严禁包含任何模型推理调用，AI 超分/抠图必须离线预处理或云端完成，"
                "交付物 `client_realtime_ai_calls` 必须为 0；"
            )
        else:
            runtime = "CoreML / ONNX Runtime / TFLite" if on_ios and on_android else (
                "ONNX Runtime / TFLite" if on_android else "CoreML / ONNX Runtime"
            )
            lines.append(
                f"client_zero_inference=false：允许端侧轻量离线模型（{runtime}），需写明模型体积、首帧耗时与耗电评估；"
            )
    elif role_code == "qa":
        if on_ios and on_android:
            lines.append("平台：iOS 与 Android 都要提审。iOS 按 App Store Review Guidelines（4.3 查重、5.1 隐私）；Android 按 Google Play Developer Policy（重复内容政策、数据安全表单）。")
        elif on_android:
            lines.append("平台：Android，提审合规按 Google Play Developer Policy（重复内容政策、数据安全表单）；严禁套用 Apple 4.3 检查。")
        else:
            lines.append("平台：iOS，提审合规按 App Store Review Guidelines（4.3 查重、5.1 隐私）。")
    return lines


def render_persona(role_code: str, persona: str, platform: Optional[str], client_zero_inference: Optional[bool]) -> str:
    lines = profile_redlines(role_code, platform, client_zero_inference)
    if not lines:
        return persona
    return persona + "\n5. 【本项目 Profile 红线】：\n" + "\n".join(f"   - {line}" for line in lines)


# ==============================================================================
# Mapping from 11 Workflow Stages to Roles and Gates (关口分级模型)
# ==============================================================================
# 级别：🟢 green (lead 自批，事后抽查) ｜ 🟡 yellow (人批，批量) ｜ 🔴 red (人必批，即时通知)
HOTFIX_GATE_CONFIG: Dict[str, Any] = {
    "name": "P0 热修关口",
    "level": "red",
    "approver": "human",
    "conditions": ["预授权仅限回滚/降级；其余人批", "24h 内补 CR 与 PRD"],
    "auto_escalate_triggers": []
}

STAGE_ROLE_CONFIGS: Dict[str, Dict[str, Any]] = {
    "01": {
        "primary": "mr",
        "collaborators": ["ba"],
        "stage_name": "市场研究",
        "execution_mode": "agent_driven",
        "mission_focus": "全球赛道摸底、真假盘面验资、流量钩子与竞品差评拆解",
        "gate": {
            "name": "门禁自检",
            "level": "green",
            "approver": "lead",
            "conditions": ["含自下而上 SOM 测算", "明确干/不干/怎么干建议", "核心数据带来源 source 或标注假设"],
            "auto_escalate_triggers": []
        }
    },
    "02": {
        "primary": "ba",
        "collaborators": ["mr"],
        "stage_name": "商业模式分析",
        "execution_mode": "agent_driven",
        "mission_focus": "变现路径、定价阶梯、单位经济模型(LTV/CAC)",
        "gate": {
            "name": "LTV/CAC 商业关口",
            "level": "yellow",
            "approver": "human",
            "conditions": ["LTV/CAC >= 3.0 且预算受控", "若 < 3.0 自动暂停"],
            "auto_escalate_triggers": ["ltv_cac_below_3", "budget_exceeded"]
        }
    },
    "03": {
        "primary": "pm",
        "collaborators": ["mr", "ba", "cmp"],
        "stage_name": "产品方向决策",
        "execution_mode": "agent_driven",
        "mission_focus": "一页纸核心卖点(UVP)、MoSCoW减法刀法与待验证生死假设清单(严禁未验先定写代码级PRD)",
        "gate": {
            "name": "G1 立项方向",
            "level": "yellow",
            "approver": "human",
            "conditions": ["一页纸精益方向卡", "H1~H4 生死假设清单明确", "cmp 初筛无红灯合规风险"],
            "auto_escalate_triggers": ["privacy_compliance_risk", "regulatory_red_flag"]
        }
    },
    "04": {
        "primary": "mkt",
        "collaborators": ["ux", "ba"],
        "stage_name": "低成本市场验证",
        "execution_mode": "hybrid",
        "mission_focus": "生成可交互H5假门着陆页原型(index.html)、3条极简测试脚本与获客红线，并在文末设立Go/Pivot/Kill立项决策门禁(需人工外测)",
        "gate": {
            "name": "G2 外测决议",
            "level": "yellow",
            "approver": "human",
            "conditions": ["ba 出具外测数据建议", "数据须来自真实外测埋点", "触碰止损线自动暂停"],
            "auto_escalate_triggers": ["fake_door_ctr_below_threshold", "cac_exceeded"]
        }
    },
    "05": {
        "primary": "pm",
        "collaborators": ["ba", "eng", "ux", "cmp"],
        "stage_name": "产品需求定义",
        "execution_mode": "hybrid",
        "mission_focus": "定义纯业务规格说明书 PRD，管理需求变更单 CR 闭环",
        "gate": {
            "name": "prd_linter 规格门禁",
            "level": "green",
            "approver": "lead",
            "conditions": ["prd_linter 满分 100", "黄金 7+1 章节完备", "无工程代码与 SQL DDL 泄露"],
            "auto_escalate_triggers": ["payment", "privacy", "user_data", "data_dictionary_schema_change"]
        }
    },
    "06": {
        "primary": "ux",
        "collaborators": ["pm"],
        "stage_name": "设计实现",
        "execution_mode": "agent_driven",
        "mission_focus": "信息架构、交互主流程原型与可用性测试用例",
        "gate": {
            "name": "HIG/Material 检测",
            "level": "green",
            "approver": "lead",
            "conditions": ["根据项目 profile 匹配规则", "iOS 灵动岛顶部安全区 >= 71pt", "触控热区 >= 44x44pt"],
            "auto_escalate_triggers": ["interaction_breaking_cr"]
        }
    },
    "07": {
        "primary": "eng",
        "collaborators": ["qa"],
        "stage_name": "开发实现",
        "execution_mode": "agent_driven",
        "mission_focus": "技术架构选型、工程骨架、接口契约规范与核心业务代码实现",
        "gate": {
            "name": "覆盖率与零推理门禁",
            "level": "green",
            "approver": "lead",
            "conditions": ["核心逻辑单测覆盖率 >= 80%", "零推理成本合规 (按 profile 决定)"],
            "auto_escalate_triggers": ["payment", "encryption", "privacy_sdk"]
        }
    },
    "08": {
        "primary": "qa",
        "collaborators": ["eng"],
        "stage_name": "测试与 QA",
        "execution_mode": "agent_driven",
        "mission_focus": "冒烟测试用例、边界条件测试与阻断性Issue审查",
        "gate": {
            "name": "G3 质量门",
            "level": "green",
            "approver": "qa",
            "conditions": ["0 个未关闭的 P0/P1 Issue", "弱网与异常场景验证通过", "抽查 qa 报告通过"],
            "auto_escalate_triggers": ["open_p0_bug", "unresolved_major_issue"]
        }
    },
    "09": {
        "primary": "qa",
        "collaborators": ["eng", "cmp"],
        "stage_name": "发布与上线",
        "execution_mode": "hybrid",
        "mission_focus": "构建包合规质检、商店元数据与发布风险检查清单",
        "gate": {
            "name": "G4 提审门禁",
            "level": "red",
            "approver": "human",
            "conditions": ["商店提审合规表无红灯 (Apple 4.3 查重/隐私协议)", "具备提审降级保护开关 Remote Config", "具备快速回滚预案", "必须有人类确认记录"],
            "auto_escalate_triggers": []
        }
    },
    "10": {
        "primary": "mkt",
        "collaborators": ["ba", "ops"],
        "stage_name": "市场推广与获客",
        "execution_mode": "agent_driven",
        "mission_focus": "ASO关键词优化、买量投放脚本与分销渠道方案",
        "gate": {
            "name": "买量预算门禁",
            "level": "yellow",
            "approver": "human",
            "conditions": ["首次投放需人批", "新市场投放需人批", "超 lead 自批额度需人批", "eCAC 熔断机制生效"],
            "auto_escalate_triggers": ["budget_exceeded", "new_market_expansion"]
        }
    },
    "11": {
        "primary": "ops",
        "collaborators": ["pm", "mkt"],
        "stage_name": "运营分析与持续迭代",
        "execution_mode": "agent_driven",
        "mission_focus": "留存漏斗复盘、核心指标监控与下一阶段迭代建议",
        "gate": {
            "name": "Backlog 评审",
            "level": "green",
            "approver": "lead",
            "conditions": ["输出数据驱动的 V1.1 Backlog", "流入工序 05 循环"],
            "auto_escalate_triggers": ["major_version_pivot", "budget_exceeded"]
        }
    }
}


def get_stage_gate_conditions(stage_code: str, platform: str = "ios", client_zero_inference: bool = True) -> List[str]:
    """
    Returns profile-parameterized gate conditions for a stage.
    Stage 06:
      - iOS: HIG conditions (Dynamic Island >=71pt, touch >=44pt)
      - Android: Material 3 conditions (status bar cutout >=24~48dp, touch >=48dp)
    Stage 07:
      - client_zero_inference=True: strict zero inference
      - client_zero_inference=False: edge AI permitted per profile
    """
    stage_cfg = STAGE_ROLE_CONFIGS.get(stage_code, {})
    gate_cfg = stage_cfg.get("gate", {})
    conditions = list(gate_cfg.get("conditions", []))
    from backend.app.services.profile_guard import covers_android, covers_ios

    if stage_code == "06":
        conditions_06: List[str] = []
        if covers_android(platform):
            conditions_06 += [
                "根据项目 profile 匹配规则 (Android Material 3)",
                "状态栏/挖孔避让安全区 >= 24~48dp",
                "触控热区 >= 48x48dp",
            ]
        if covers_ios(platform):
            conditions_06 += [
                "根据项目 profile 匹配规则 (iOS HIG)",
                "iOS 灵动岛顶部安全区 >= 71pt",
                "触控热区 >= 44x44pt",
            ]
        return conditions_06
    elif stage_code == "07":
        if client_zero_inference:
            return [
                "核心逻辑单测覆盖率 >= 80%",
                "零推理成本合规 (强制零推理 client_zero_inference=True)"
            ]
        else:
            return [
                "核心逻辑单测覆盖率 >= 80%",
                "端侧推理合规 (按 profile 允许端侧本地模型 client_zero_inference=False)"
            ]
    return conditions

async def seed_agent_roles_if_empty(db: AsyncSession):
    """Ensure all 8 core agent roles exist in database, updating or inserting them."""
    for role_data in DEFAULT_AGENT_ROLES:
        stmt = select(AgentRoleDefinition).where(AgentRoleDefinition.role_code == role_data["role_code"])
        res = await db.execute(stmt)
        existing = res.scalar_one_or_none()
        if not existing:
            role_obj = AgentRoleDefinition(
                id=role_data["id"],
                role_code=role_data["role_code"],
                name=role_data["name"],
                title=role_data["title"],
                avatar_icon=role_data["avatar_icon"],
                color=role_data["color"],
                responsibilities=role_data["responsibilities"],
                system_persona=role_data["system_persona"],
                allowed_tools=role_data["allowed_tools"],
                preferred_executor=role_data["preferred_executor"]
            )
            db.add(role_obj)
        else:
            # Update fields in case persona or title were enhanced
            existing.name = role_data["name"]
            existing.title = role_data["title"]
            existing.avatar_icon = role_data["avatar_icon"]
            existing.color = role_data["color"]
            existing.responsibilities = role_data["responsibilities"]
            existing.system_persona = role_data["system_persona"]
            existing.allowed_tools = role_data["allowed_tools"]
            db.add(existing)

    await db.commit()

async def get_module_role_bundle(db: AsyncSession, module_code: str) -> Dict[str, Any]:
    """Retrieve primary role and collaborator roles definitions for a given module code."""
    config = STAGE_ROLE_CONFIGS.get(module_code, {
        "primary": "pm",
        "collaborators": [],
        "stage_name": "工序",
        "mission_focus": "业务交付物推演"
    })
    
    role_codes = [config["primary"]] + config["collaborators"]
    stmt = select(AgentRoleDefinition).where(AgentRoleDefinition.role_code.in_(role_codes))
    res = await db.execute(stmt)
    roles_list = res.scalars().all()
    roles_by_code = {r.role_code: r for r in roles_list}

    primary_role = roles_by_code.get(config["primary"])
    collab_roles = [roles_by_code[c] for c in config["collaborators"] if c in roles_by_code]

    return {
        "config": config,
        "primary_role": primary_role,
        "collaborator_roles": collab_roles
    }

async def migrate_db_for_roles(db: AsyncSession):
    """Safely adds missing role, execution mode, and bundle artifact columns to SQLite database."""
    try:
        # 1. ModuleInstance columns
        mod_cols = (await db.execute(text("PRAGMA table_info(module_instances)"))).fetchall()
        existing_mod_col_names = [col[1] for col in mod_cols]

        if "primary_role_code" not in existing_mod_col_names:
            await db.execute(text("ALTER TABLE module_instances ADD COLUMN primary_role_code VARCHAR(30) DEFAULT 'pm'"))
        if "collaborator_role_codes" not in existing_mod_col_names:
            await db.execute(text("ALTER TABLE module_instances ADD COLUMN collaborator_role_codes JSON DEFAULT '[]'"))
        if "execution_mode" not in existing_mod_col_names:
            await db.execute(text("ALTER TABLE module_instances ADD COLUMN execution_mode VARCHAR(20) DEFAULT 'agent_driven'"))
        if "synced_upstream_versions" not in existing_mod_col_names:
            await db.execute(text("ALTER TABLE module_instances ADD COLUMN synced_upstream_versions JSON DEFAULT '{}'"))

        run_cols = (await db.execute(text("PRAGMA table_info(workflow_runs)"))).fetchall()
        if "auto_advance" not in [col[1] for col in run_cols]:
            await db.execute(text("ALTER TABLE workflow_runs ADD COLUMN auto_advance BOOLEAN DEFAULT 1"))

        # 2. SessionMessage columns
        msg_cols = (await db.execute(text("PRAGMA table_info(session_messages)"))).fetchall()
        existing_msg_col_names = [col[1] for col in msg_cols]

        if "role_code" not in existing_msg_col_names:
            await db.execute(text("ALTER TABLE session_messages ADD COLUMN role_code VARCHAR(30) DEFAULT NULL"))

        # 3. Artifact columns
        art_cols = (await db.execute(text("PRAGMA table_info(artifacts)"))).fetchall()
        existing_art_col_names = [col[1] for col in art_cols]

        if "artifact_type" not in existing_art_col_names:
            await db.execute(text("ALTER TABLE artifacts ADD COLUMN artifact_type VARCHAR(20) DEFAULT 'markdown'"))
        if "storage_rel_path" not in existing_art_col_names:
            await db.execute(text("ALTER TABLE artifacts ADD COLUMN storage_rel_path VARCHAR(255) DEFAULT NULL"))
        if "entry_file" not in existing_art_col_names:
            await db.execute(text("ALTER TABLE artifacts ADD COLUMN entry_file VARCHAR(50) DEFAULT 'index.html'"))
        if "change_summary" not in existing_art_col_names:
            await db.execute(text("ALTER TABLE artifacts ADD COLUMN change_summary TEXT DEFAULT NULL"))

        # 4. Unique index on artifacts(module_id, version)
        try:
            await db.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_module_artifact_version ON artifacts(module_id, version)"))
        except Exception:
            pass

        # 5. Product shadow_mode & profile columns
        prod_cols = (await db.execute(text("PRAGMA table_info(products)"))).fetchall()
        existing_prod_col_names = [col[1] for col in prod_cols]
        if "shadow_mode" not in existing_prod_col_names:
            await db.execute(text("ALTER TABLE products ADD COLUMN shadow_mode BOOLEAN DEFAULT 1"))
        if "platform" not in existing_prod_col_names:
            await db.execute(text("ALTER TABLE products ADD COLUMN platform VARCHAR(30) DEFAULT 'ios'"))
        if "client_zero_inference" not in existing_prod_col_names:
            await db.execute(text("ALTER TABLE products ADD COLUMN client_zero_inference BOOLEAN DEFAULT 1"))

        # 6. GateApplication shadow tracking columns
        gate_cols = (await db.execute(text("PRAGMA table_info(gate_applications)"))).fetchall()
        existing_gate_col_names = [col[1] for col in gate_cols]
        if "lead_recommendation" not in existing_gate_col_names:
            await db.execute(text("ALTER TABLE gate_applications ADD COLUMN lead_recommendation VARCHAR(20) DEFAULT NULL"))
        if "lead_rationale" not in existing_gate_col_names:
            await db.execute(text("ALTER TABLE gate_applications ADD COLUMN lead_rationale TEXT DEFAULT NULL"))
        if "is_consistent" not in existing_gate_col_names:
            await db.execute(text("ALTER TABLE gate_applications ADD COLUMN is_consistent BOOLEAN DEFAULT NULL"))

        setting_cols = (await db.execute(text("PRAGMA table_info(agent_settings)"))).fetchall()
        if setting_cols and "cli_model" not in [col[1] for col in setting_cols]:
            await db.execute(text("ALTER TABLE agent_settings ADD COLUMN cli_model VARCHAR(120) DEFAULT NULL"))

        # 7. Create lead_shadow_decisions table if not exists
        await db.execute(text("""
            CREATE TABLE IF NOT EXISTS lead_shadow_decisions (
                id VARCHAR PRIMARY KEY,
                product_id VARCHAR NOT NULL REFERENCES products(id),
                module_id VARCHAR REFERENCES module_instances(id),
                gate_application_id VARCHAR REFERENCES gate_applications(id),
                decision_type VARCHAR(30) NOT NULL DEFAULT 'gate_review',
                stage_code VARCHAR(10),
                lead_recommendation VARCHAR(20) NOT NULL,
                lead_rationale TEXT,
                human_decision VARCHAR(20),
                human_feedback TEXT,
                human_reviewer VARCHAR(50),
                is_consistent BOOLEAN,
                resolved_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """))

        # 8. Create hotfix_followup_tasks table if not exists (Phase 7)
        await db.execute(text("""
            CREATE TABLE IF NOT EXISTS hotfix_followup_tasks (
                id VARCHAR PRIMARY KEY,
                run_id VARCHAR NOT NULL REFERENCES workflow_runs(id),
                product_id VARCHAR NOT NULL REFERENCES products(id),
                task_type VARCHAR(30) NOT NULL,
                title VARCHAR(200) NOT NULL,
                description TEXT,
                status VARCHAR(20) NOT NULL DEFAULT 'pending',
                deadline DATETIME NOT NULL,
                completed_at DATETIME,
                completed_by VARCHAR(50),
                notes TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """))

        await db.commit()

        # 5. Update existing module instances to reflect their stage role configs & execution mode
        mod_stmt = select(ModuleInstance)
        res = await db.execute(mod_stmt)
        modules = res.scalars().all()
        for m in modules:
            cfg = STAGE_ROLE_CONFIGS.get(m.module_code)
            if cfg:
                m.primary_role_code = cfg["primary"]
                m.collaborator_role_codes = cfg["collaborators"]
                m.execution_mode = cfg.get("execution_mode", "agent_driven")
                if not m.synced_upstream_versions:
                    m.synced_upstream_versions = {}
                db.add(m)
        await db.commit()
    except Exception as e:
        print(f"[migrate_db_for_roles] Notice: {e}")

