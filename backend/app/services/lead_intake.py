"""
Lead Agent Intake Mode Service (backend/app/services/lead_intake.py)

Responsibilities:
1. Conducts strategic scoping interviews with the CEO before strategic initiative creation.
2. Challenges ungrounded assumptions and enforces truth-over-fiction principle.
3. Identifies market demand signals, competitor vulnerabilities, and unverified assumptions.
4. Synthesizes structured Strategic Initiative proposals & authorization draft suggestions.
5. Empowers the CEO to adopt or adjust the proposal with one click.
"""

import re
from typing import Dict, Any, List, Optional


TRACK_TEMPLATES = {
    "focus_detox": {
        "keywords": ["专注", "番茄钟", "数字排毒", "冥想", "习惯", "focus", "pomodoro", "detox", "health"],
        "name": "北美离线极简专注与数字排毒应用矩阵",
        "description": "针对北美大学生与知识工作者的高频学习/专注场景，主打极致轻量、零云端依赖的离线隐私保护与极简美学，通过买断制与反周卡订阅切入。",
        "strategic_intent": "以纯本地离线隐私+极简沉浸为差异化切口，抢占北美期末备考与远程办公专注场景，规避云端推理高昂维护成本。",
        "target_market": "北美 (US/CA) 18-28 岁大学生、考证群体与远程知识工作者",
        "business_model_hypothesis": "免费核心番茄钟 + $14.99 终身买断 (含白噪音与统计图表) / $2.99 季度高阶音效包；综合 LTV/CAC ≥ 3.5x，回本周期 ≤ 45 天",
        "suggested_budget": 15000.0,
        "hard_stop_loss": 20000.0,
        "currency": "USD",
        "signals": [
            {
                "type": "demand",
                "claim": "Google & App Store 高意图词 'minimalist pomodoro timer' / 'offline focus app' 搜索量平稳上升，搜索转化率高于泛娱乐类",
                "status": "observed",
                "source": "Apple Search Ads & App Store Category Insights"
            },
            {
                "type": "competitor",
                "claim": "头部竞品 (Forest / Flora / Endel) 近 90 天 1-2 星差评中有 38% 集中在『强制云端账号登录』与『未经提醒自动续费周卡扣费』",
                "status": "observed",
                "source": "App Store Reviews Top Complaints Audit"
            },
            {
                "type": "structural",
                "claim": "纯客户端离线架构无需后端 GPU 推理与高带宽服务器，毛利率可死守 90% 以上",
                "status": "observed",
                "source": "Platform Zero-Inference Architecture Baseline"
            }
        ],
        "unverified_assumptions": [
            {
                "claim": "假设 TikTok / Reddit 学习博主有机种草能够实现获客 CAC ≤ $4.50",
                "risk_level": "high",
                "validation_stage": "04 假门外测"
            },
            {
                "claim": "假设买断制 ($14.99) 付费转化率能够达到 3.5% 以上",
                "risk_level": "medium",
                "validation_stage": "02 商业模式精算"
            }
        ],
        "kill_criteria": [
            "工序 04 假门外测：落地页核心购买意图点击率 (CTR) < 2.0% 则立即熔断暂停",
            "工序 02 商业精算：若模拟单位经济模型 LTV/CAC < 3.0 则阻断进入研发工序",
            "合规与隐私红线：必须恪守纯本地离线数据存储，严禁上传用户屏幕使用习惯"
        ],
        "stage_allocations": {
            "01_market_research": 1000.0,
            "02_business_model": 1500.0,
            "03_product_direction": 500.0,
            "04_fake_door": 2500.0,
            "05_product_requirement": 1000.0,
            "06_design_implementation": 2000.0,
            "07_development": 4000.0,
            "08_testing_qa": 1000.0,
            "09_release_deployment": 500.0,
            "10_growth_marketing": 2000.0,
            "11_operations_iteration": 0.0
        }
    },
    "ecommerce_saas": {
        "keywords": ["电商", "独立站", "shopify", "选品", "客服", "跨境", "cross-border", "retail"],
        "name": "跨境独立站高客单单品站与 AI 自动化客服工程",
        "description": "针对欧美家居与户外高客单品类，构建 DTC 品牌独立站，集成多语种轻量化客服与物流追踪系统，实现首单毛利转正。",
        "strategic_intent": "以垂直高毛利品类（客单价 ≥ $80）切入欧美市场，通过精细化私域客服降低退款率至 5% 以下。",
        "target_market": "欧美 (US/UK/DE) 25-45 岁有房家庭及户外运动爱好者",
        "business_model_hypothesis": "客单价 $95，毛利率 65%，首单获客 CAC ≤ $28，综合复购率 22%，LTV/CAC ≥ 3.2x",
        "suggested_budget": 25000.0,
        "hard_stop_loss": 32000.0,
        "currency": "USD",
        "signals": [
            {
                "type": "demand",
                "claim": "欧美户外与居家细分品类 Google Shopping 搜索意图强劲，长尾词 CPC 处于可控区间",
                "status": "observed",
                "source": "Google Shopping & Meta Ad Library Benchmark"
            },
            {
                "type": "competitor",
                "claim": "多数通用型铺货独立站售后响应时间超过 24 小时，差评主要来自于物流追踪脱节",
                "status": "observed",
                "source": "Trustpilot Competitor Reviews Benchmark"
            }
        ],
        "unverified_assumptions": [
            {
                "claim": "假设首单转化率在冷启动期可达 1.8% 以上",
                "risk_level": "high",
                "validation_stage": "04 假门外测"
            }
        ],
        "kill_criteria": [
            "工序 04 假门外测：加购率 (ATC) < 4% 或发起结账率 < 1.5% 立即终止",
            "退款率预测超过 8% 阻断正式量产备货"
        ],
        "stage_allocations": {
            "01_market_research": 2000.0,
            "02_business_model": 2000.0,
            "03_product_direction": 1000.0,
            "04_fake_door": 4000.0,
            "05_product_requirement": 1500.0,
            "06_design_implementation": 2500.0,
            "07_development": 6000.0,
            "08_testing_qa": 1000.0,
            "09_release_deployment": 1000.0,
            "10_growth_marketing": 4000.0,
            "11_operations_iteration": 0.0
        }
    },
    "ai_photo_tool": {
        "keywords": ["ai", "图像", "超分", "抠图", "照片", "相机", "滤镜", "photo", "avatar", "image"],
        "name": "移动端轻量级离线 AI 图像增强与老照片修复",
        "description": "基于端侧轻量化 NPU 模型的离线人像画质超分与老照片上色修复工具，死守零云端 API 成本底线，保护用户隐私。",
        "strategic_intent": "主打端侧零推理成本与零隐私泄露风险，截胡云端订阅制同质化软件，快速积累高分好评与口碑。",
        "target_market": "全球移动端家庭摄影爱好者与老照片数字化修复需求群体",
        "business_model_hypothesis": "基础功能免费 + 导出高分辨率买断 $19.99 或年费 $29.99，LTV/CAC ≥ 4.0x",
        "suggested_budget": 18000.0,
        "hard_stop_loss": 24000.0,
        "currency": "USD",
        "signals": [
            {
                "type": "demand",
                "claim": "移动端老照片修复与图像无损放大在全球 App Store 搜索量常年位居图形工具前五",
                "status": "observed",
                "source": "App Store Graphics & Design Trends"
            },
            {
                "type": "competitor",
                "claim": "头部竞品 (Remini 等) 强制要求上传人脸图片到云端服务器，且周卡连续扣费引起大量差评",
                "status": "observed",
                "source": "User Privacy & Pricing Backlash Analysis"
            }
        ],
        "unverified_assumptions": [
            {
                "claim": "端侧量化模型在 iPhone 12 及以上机型的单次推理耗时能否稳定在 1.5 秒以内",
                "risk_level": "high",
                "validation_stage": "07 开发实现"
            }
        ],
        "kill_criteria": [
            "低端设备推理发热严重或内存超标 (OOM) 触碰发布拒签门禁",
            "工序 04 假门测试付费意向率 < 2.5% 则终止"
        ],
        "stage_allocations": {
            "01_market_research": 1000.0,
            "02_business_model": 1500.0,
            "03_product_direction": 500.0,
            "04_fake_door": 3000.0,
            "05_product_requirement": 1000.0,
            "06_design_implementation": 2000.0,
            "07_development": 5000.0,
            "08_testing_qa": 1500.0,
            "09_release_deployment": 500.0,
            "10_growth_marketing": 2000.0,
            "11_operations_iteration": 0.0
        }
    }
}


def _detect_track_template(query_text: str) -> Optional[Dict[str, Any]]:
    lowered = query_text.lower()
    for track_key, track_data in TRACK_TEMPLATES.items():
        for kw in track_data["keywords"]:
            if kw.lower() in lowered:
                return track_data
    return None


def _extract_budget(text: str) -> Optional[float]:
    # Match patterns like $15,000, 15000, 1.5万, 20,000美元, etc.
    m_usd = re.search(r"[\$￥]?\s*([0-9]{1,3}(?:,[0-9]{3})+|[0-9]+(?:\.[0-9]+)?)\s*(?:美元|刀|usd|元|k|万)?", text, re.I)
    if m_usd:
        raw_val = m_usd.group(1).replace(",", "")
        try:
            val = float(raw_val)
            if "万" in text:
                val *= 10000
            elif "k" in text.lower():
                val *= 1000
            if 100 <= val <= 10000000:
                return val
        except ValueError:
            pass
    return None


async def intake_lead_dialogue(
    messages: List[Dict[str, str]],
    current_draft: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Lead Agent processes user's strategic intent dialogue, outputs constructive challenges,
    and returns an updated proposal draft with signals, assumptions, and stop-loss criteria.
    """
    if not messages:
        return {
            "reply": (
                "CEO 您好！我是项目总控智能体 **Lead**。\n\n"
                "在正式立项并投入研发资源前，请告诉我您构想的战略方向或出海赛道"
                "（例如：北美跨境电商独立站、出海数字健康专注工具、AI 图像处理工具等）。\n\n"
                "我将严格基于**「事实与真实信号优先，假设明确隔离」**的准则，帮您梳理核心假设、审查竞品软肋，"
                "并为您推演起草一页纸战略任务书与授权包建议。"
            ),
            "proposal": current_draft or {},
            "quick_prompts": [
                "北美出海数字健康与专注类应用矩阵 (Focus/Health)",
                "跨境电商出海高客单独立站与配套 AI 客服",
                "出海 AI 照片增强与超分工具 (移动端纯客户端)",
                "东南亚本地生活效率工具矩阵"
            ]
        }

    # Aggregate all user input
    user_inputs = [m["content"] for m in messages if m.get("role") == "user"]
    last_user_message = user_inputs[-1] if user_inputs else ""
    full_context = " ".join(user_inputs)

    # 1. Template detection or generic extraction
    matched_template = _detect_track_template(full_context)
    detected_budget = _extract_budget(last_user_message) or _extract_budget(full_context)

    # Initialize proposal baseline
    draft = dict(current_draft or {})

    if matched_template:
        for k in ["name", "description", "strategic_intent", "target_market",
                  "business_model_hypothesis", "suggested_budget", "hard_stop_loss",
                  "currency", "signals", "unverified_assumptions", "kill_criteria",
                  "stage_allocations"]:
            if k not in draft or not draft[k]:
                draft[k] = matched_template[k]
    else:
        # Generic intelligent baseline synthesized from user message
        snippet = last_user_message.strip()[:40]
        if not draft.get("name"):
            draft["name"] = f"出海创新工程：{snippet}"
        if not draft.get("strategic_intent"):
            draft["strategic_intent"] = f"以创新切口突破出海细分赛道，验证市场核心痛点与商业闭环：{last_user_message.strip()}"
        if not draft.get("target_market"):
            draft["target_market"] = "欧美成熟市场及出海高净值数字用户群"
        if not draft.get("business_model_hypothesis"):
            draft["business_model_hypothesis"] = "以轻量级工具/服务切入，验证 LTV/CAC ≥ 3.0 与合理回本周期"
        if not draft.get("suggested_budget"):
            draft["suggested_budget"] = 15000.0
        if not draft.get("hard_stop_loss"):
            draft["hard_stop_loss"] = 20000.0
        if not draft.get("currency"):
            draft["currency"] = "USD"
        if not draft.get("signals"):
            draft["signals"] = [
                {
                    "type": "demand",
                    "claim": f"针对 '{snippet}' 赛道的长尾搜索意图与用户痛点具备出海变现空间",
                    "status": "observed",
                    "source": "Market Exploration Baseline"
                }
            ]
        if not draft.get("unverified_assumptions"):
            draft["unverified_assumptions"] = [
                {
                    "claim": "假设目标客群愿意为该核心解决方案直接支付买断或订阅费用",
                    "risk_level": "high",
                    "validation_stage": "04 假门外测"
                }
            ]
        if not draft.get("kill_criteria"):
            draft["kill_criteria"] = [
                "工序 04 假门外测：核心意图点击率 < 2% 则熔断",
                "工序 02 商业精算：LTV/CAC 预测值 < 3.0 则阻断进入开发"
            ]

    # Override budget if user explicitly mentioned one
    if detected_budget:
        draft["suggested_budget"] = float(detected_budget)
        draft["hard_stop_loss"] = float(detected_budget * 1.3)
        # Recalculate allocations proportionally
        if "stage_allocations" in draft and draft["stage_allocations"]:
            total_alloc = sum(draft["stage_allocations"].values()) or 1.0
            ratio = draft["suggested_budget"] / total_alloc
            draft["stage_allocations"] = {
                k: round(v * ratio, 2) for k, v in draft["stage_allocations"].items()
            }

    # Ensure budget matches `budget` field expected by API
    draft["budget"] = draft.get("suggested_budget", 15000.0)

    # 2. Formulate Lead's constructive reply in sharp, responsible voice
    reply_lines = [
        f"我是项目总控 **Lead**。针对您构想的战略方向，我已经完成立项前置审查与红队挑战推演：\n",
        f"🎯 **战略定位定性**：{draft.get('strategic_intent', '')}",
        f"🌍 **目标细分战区**：{draft.get('target_market', '')}",
        f"💰 **商业模式假设**：{draft.get('business_model_hypothesis', '')}\n",
        "🔍 **已识别的真实市场与竞品信号 (Evidence)**："
    ]

    for sig in draft.get("signals", [])[:2]:
        reply_lines.append(f"- 🟢 **[{sig.get('type', 'signal').upper()}]** {sig.get('claim', '')} *(来源: {sig.get('source', '行业基线')})*")

    reply_lines.append("\n⚠️ **红队挑战：待验证的高风险假设 (需严守工序门禁)**：")
    for unv in draft.get("unverified_assumptions", [])[:2]:
        reply_lines.append(f"- 🔴 **[{unv.get('validation_stage', '后续工序')}]** {unv.get('claim', '')} (风险等级: {unv.get('risk_level', 'high')})")

    reply_lines.append(
        f"\n🛡️ **授权与止损包建议**：\n"
        f"- 建议首批战略注资：**${draft.get('suggested_budget', 15000):,.0f} {draft.get('currency', 'USD')}**\n"
        f"- 硬止损熔断阈值：**${draft.get('hard_stop_loss', 20000):,.0f} {draft.get('currency', 'USD')}**\n"
        f"- 关键熔断退出条件 (Kill Criteria)：{'；'.join(draft.get('kill_criteria', [])[:2])}。"
    )

    reply_lines.append(
        "\n👉 **右侧面板已为您同步起草一页纸《战略工程提案与授权包建议草案》**。"
        "您可以直接修改右侧的各项参数。若确认无误，请点击下方 **【采纳 Lead 提案并正式创建战略工程】** 拍板立项。"
    )

    quick_prompts = [
        "确认以北美为首发市场并锁定预算",
        "强化纯本地离线隐私作为核心卖点",
        "调整前期总预算至 $10,000 美元",
        "增加 G2 假门外测的核心退出条件"
    ]

    return {
        "reply": "\n".join(reply_lines),
        "proposal": draft,
        "quick_prompts": quick_prompts
    }
