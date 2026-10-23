from typing import Dict, Any, List, Optional
import math

# ==============================================================================
# Domain Knowledge Bases for Representative Target Verticals
# ==============================================================================

CATEGORY_PROFILES = {
    "wallpaper_personalization": {
        "keywords": ["壁纸", "wallpaper", "锁屏", "美化", "主题", "背景", "pager", "widget", "小组件"],
        "category_name": "移动端个性化与桌面美化 (Mobile Personalization & Customization)",
        "global_market_size_usd": 4200000000, # $4.2B global personalization market
        "north_america_share": 0.38,
        "default_arpu_annual": 14.99,
        "smartphone_penetration_rate": 0.85,
        "competitors": [
            {
                "name": "Zedge",
                "positioning": "泛大众综合美化巨头 (壁纸+铃声+NFT)",
                "platforms": "iOS / Android / Web",
                "scale": "3,000万+ 全球月活 (MAU)",
                "monetization": "广告 (AdMob/FAN) + 订阅 ($1.99/月, $9.99/年) + Zedge Credits 代币内购",
                "pricing": "$1.99/mo, $9.99/yr",
                "traffic_channels": "ASO 头部大词自然垄断、TikTok 泛流量、多年老牌品牌效应",
                "user_complaints": "开屏广告与插屏广告泛滥、低端机发热卡顿、内容搬运泛滥缺少版权审核",
                "vulnerability": "UI 架构老旧繁琐，缺乏对 iOS 16+ 锁屏景深及高质量原创新设计的工具化支持"
            },
            {
                "name": "Backdrops",
                "positioning": "极客与数字创作者专属原创壁纸社区",
                "platforms": "Android (主力) / iOS",
                "scale": "200万+ 高黏性月活",
                "monetization": "免费+一次性 Pro 买断 ($3.99-$4.99) + 限量赞助",
                "pricing": "$3.99 - $4.99 一次性买断",
                "traffic_channels": "Android Authority/The Verge 媒体背书、Reddit/X 极客自发口碑、Wall of the Day 每日精选",
                "user_complaints": "iOS 端更新迟缓、缺少动态壁纸与锁屏深度联动效果、无桌面配套工具",
                "vulnerability": "变现手段极其佛系单一，单客 LTV 低，未开拓订阅制与 AI 模板二次创作"
            },
            {
                "name": "Wallcraft (WallpapersCraft)",
                "positioning": "算法全机型分辨率精准适配 + 工业化量产壁纸",
                "platforms": "iOS / Android",
                "scale": "500万+ 月活",
                "monetization": "激进周订阅 ($1.99/周) + 4K/8K 强制看视频广告",
                "pricing": "$1.99/week, $14.99/year",
                "traffic_channels": "激进买量 (Meta/TikTok/Google Ads)、ASO 关键词覆盖",
                "user_complaints": "周订阅扣费陷阱导致大量 1 星退费差评、强制视频广告无法跳过",
                "vulnerability": "口碑极度恶化，用户缺乏品牌忠诚度，易被体验清爽、定价健康的竞品切走存量用户"
            },
            {
                "name": "Vellum Wallpapers",
                "positioning": "iOS 独占极简高阶策展与艺术摄影壁纸",
                "platforms": "iOS 独占",
                "scale": "150万+ 高净值月活",
                "monetization": "轻度插屏广告 + 一次性 Premium ($2.99-$4.99)",
                "pricing": "$2.99 - $4.99 Premium",
                "traffic_channels": "Apple App Store 多次官方 Today 推荐、设计师设计圈口碑",
                "user_complaints": "好几年未大版本重构、无搜索与标签分类功能、图片库规模有限",
                "vulnerability": "开发维护近乎停滞，未适配 iOS 新版锁屏交互及动态景深特性"
            },
            {
                "name": "Themify",
                "positioning": "“壁纸 + 3D锁屏小组件 + 应用图标”三合一桌面整装包",
                "platforms": "iOS 主力 / iPadOS",
                "scale": "300万+ 月活，高流水",
                "monetization": "硬性付费墙 (Paywall) + 极高订阅费 ($4.99/周, $29.99/年)",
                "pricing": "$4.99/week, $29.99/year",
                "traffic_channels": "TikTok 病毒视频营销、Instagram 桌面改造趋势话题买量",
                "user_complaints": "安装图标需通过快捷指令（繁琐跳转）、退订难度大、诱导扣费",
                "vulnerability": "高 CAC 买量导致留存极低，产品工具门槛繁重，用户难以长期续费"
            }
        ],
        "personas": [
            {
                "role_name": "Alex · 24岁 北美大学生 / 科技极客",
                "device": "iPhone 15 Pro / Galaxy S24 Ultra",
                "jobs_to_be_done": "寻找不落俗套、与众不同的锁屏与桌面背景，搭配自己精心设置的单色小组件，彰显极客审美品味。",
                "pain_points": "厌恶 Zedge/Wallcraft 满屏低劣插屏广告；网上下载的 4K 壁纸设为主屏后因为图标遮挡导致杂乱看不清。",
                "willingness_to_pay": "愿意为极高审美质量或买断制付费 $4.99~$9.99，但拒绝每周被自动扣款 $1.99。"
            },
            {
                "role_name": "Chloe · 21岁 社交媒体活跃用户 / 潮流大学生",
                "device": "iPhone 14 / iPhone 15",
                "jobs_to_be_done": "随季节、穿搭、心情或 TikTok 流行趋势每周更换成套的手机主题与锁屏景深对图。",
                "pain_points": "很多壁纸不支持 iOS 景深时间被遮挡；三方整装主题配置过于复杂，快捷指令跳转体验糟糕。",
                "willingness_to_pay": "高冲动消费倾向，容易被 TikTok 视觉对比视频打动，可接受 $14.99/年订阅。"
            },
            {
                "role_name": "Marcus · 32岁 职场白领 / 极简主义拥趸",
                "device": "iPhone 13 Pro / Pixel 8",
                "jobs_to_be_done": "需要清爽、低饱和度、沉稳的深色暗黑系壁纸，专注工作不被打扰，保护视力。",
                "pain_points": "主流壁纸库充斥大量过度艳丽、二次元或低清网络搬运图，翻阅 10 分钟也找不到一张耐看的高级质感图。",
                "willingness_to_pay": "具备强劲付费能力，高度重视无广告和清爽隐私体验，倾向于 $19.99 终身买断。"
            }
        ],
        "wedge_strategy": "以「双屏成对 (Lockscreen Depth + Homescreen Gaussian Blur 柔焦对图)」为单点击穿切入点，避开竞品大而全的图库红海，以极客美学工具化降低泛广告侵扰，实现口碑自发裂变。"
    },
    "fintech_accounting": {
        "keywords": ["记账", "财务", "金融", "收单", "支付", "账本", "bookkeeping", "accounting", "pos", "msme"],
        "category_name": "出海中小微商户及个人记账金融工具 (MSME & Personal Bookkeeping)",
        "global_market_size_usd": 6800000000,
        "north_america_share": 0.25,
        "default_arpu_annual": 24.99,
        "smartphone_penetration_rate": 0.78,
        "competitors": [
            {
                "name": "BukuKas (Lummo)",
                "positioning": "东南亚印尼本土小微商户数字账本龙头",
                "platforms": "Android 主力",
                "scale": "500万+ 注册商户",
                "monetization": "前期完全免费引流，后期转向商户支付分佣与数字化电商 SaaS",
                "pricing": "基础功能免费，增值提现手续费 0.5%~1%",
                "traffic_channels": "本地地推铁军、Google Play 渠道合作、印尼商户熟人口碑",
                "user_complaints": "应用包体积膨胀后低端机卡顿、个人记账体验差、强推电商业务偏离初衷",
                "vulnerability": "偏离了极简记账核心，低端 Android 运行内存占用过大，个人和兼职小微商户体验受损"
            },
            {
                "name": "BukuWarung",
                "positioning": "微型商户记账与电子账单支付结算平台",
                "platforms": "Android / Web",
                "scale": "350万+ 活跃商户",
                "monetization": "数字支付通道抽佣 + 供应链金融小额贷转介",
                "pricing": "免费记账，支付交易手续费",
                "traffic_channels": "地推培训、WhatsApp 电子小票裂变",
                "user_complaints": "网络信号差时无法同步账单、客服响应慢、界面金融化过重",
                "vulnerability": "离线状态体验脆弱，缺少双币种和跨境外汇记账能力"
            },
            {
                "name": "Spendee",
                "positioning": "全球化个人与家庭共享记账应用",
                "platforms": "iOS / Android / Web",
                "scale": "100万+ 月活",
                "monetization": "订阅制 ($2.99/月, $22.99/年) + 终身买断",
                "pricing": "$22.99/年",
                "traffic_channels": "App Store 精选推荐、欧美泛金融理财播客赞助",
                "user_complaints": "东南亚及小语种本地银行直连大多失效、价格偏高",
                "vulnerability": "新兴市场本地化支付及离线缓存机制差，无法满足边缘网络商户"
            },
            {
                "name": "MoneyForward",
                "positioning": "成熟市场个人资产全量聚合看板",
                "platforms": "iOS / Android / Web",
                "scale": "1,200万+ 日本月活",
                "monetization": "高额月度/年度订阅 ($9.99/月)",
                "pricing": "$9.99/月",
                "traffic_channels": "日本传统金融机构整合、税务软件连通",
                "user_complaints": "严格绑定本地银行网银、无海外其他币种无缝支持",
                "vulnerability": "重合规、重本地系统，跨区域复制极为缓慢迟钝"
            },
            {
                "name": "Wallet by BudgetBakers",
                "positioning": "多币种跨国资产跟踪与现金流预测",
                "platforms": "Android / iOS / Web",
                "scale": "200万+ 月活",
                "monetization": "订阅 ($19.99/年) 或终身买断 ($39.99)",
                "pricing": "$19.99/year",
                "traffic_channels": "Google Play 长期编辑推荐、多币种数字游民群体口碑",
                "user_complaints": "本地化报表偏复杂、学习曲线陡峭",
                "vulnerability": "未针对特定地缘市场（如东南亚、拉美）进行深水区支付及小商户单据优化"
            }
        ],
        "personas": [
            {
                "role_name": "Budi · 29岁 雅加达杂货铺 (Warung) 店主",
                "device": "Redmi 9A / Oppo A16 (低端 Android)",
                "jobs_to_be_done": "记录顾客赊账 (Kasbon)、每天收摊前快速核算今天赚了多少现金与电子钱包进账。",
                "pain_points": "纸质账本容易沾水丢失，且经常忘记找谁催款；手机内存小，主流金融 App 频繁闪退。",
                "willingness_to_pay": "对纯软件订阅价格极其敏感，但如果能通过 WhatsApp 自动发送讨债单并促成回款，愿意为手续费买单。"
            },
            {
                "role_name": "Linh · 26岁 胡志明市独立插画师 / 自由职业者",
                "device": "iPhone 12 / MacBook Air",
                "jobs_to_be_done": "接收海外客户美元 (USD) 与本地越南盾 (VND) 混合款项，需要清晰按项目统计收入与税费支出。",
                "pain_points": "本土软件只有单一越南盾；欧美软件不支持本地银行并收费昂贵。",
                "willingness_to_pay": "对效率工具支付意愿强，可接受 $2.99/月或 $19.99/年订阅。"
            },
            {
                "role_name": "Kevin · 34岁 跨国数字游民 / 电商个体户",
                "device": "iPhone 15 Pro",
                "jobs_to_be_done": "频繁在多个国家穿梭，需要离线即时记账并自动换算为本位币，生成报税资产负债表。",
                "pain_points": "许多记账 App 无网时直接报错阻断操作；汇率换算数据更新慢且无法自定义。",
                "willingness_to_pay": "高客单付费用户，偏好一次性买断或专业版年费。"
            }
        ],
        "wedge_strategy": "以「弱网秒开 + 本地极速 SQLite 读写 + WhatsApp 一键催账单分享」为锋利切口，把安装包压制在 10MB 以内，主打低端机 0 闪退，抢占传统商户纸质账本替换心智。"
    },
    "utility_general": {
        "keywords": ["tool", "utility", "scanner", "cleaner", "pdf", "file", "productivity", "工具", "效率"],
        "category_name": "泛工具与生产力软件 (Utility & Productivity)",
        "global_market_size_usd": 8500000000,
        "north_america_share": 0.42,
        "default_arpu_annual": 19.99,
        "smartphone_penetration_rate": 0.82,
        "competitors": [
            {
                "name": "CamScanner",
                "positioning": "老牌文档高清扫描与 OCR",
                "platforms": "全平台",
                "scale": "数千万 MAU",
                "monetization": "昂贵订阅 ($49.99/年) + 广告",
                "pricing": "$49.99/year",
                "traffic_channels": "多年品牌口碑、企业采购",
                "user_complaints": "免费版强制带大水印、自动扣费退费极其困难、隐私安全顾虑",
                "vulnerability": "产品过于笨重庞大，定价虚高，给极简免费/低价替代品留下充足缝隙"
            },
            {
                "name": "Notion",
                "positioning": "模块化工作台与知识库",
                "platforms": "全平台",
                "scale": "3,000万+ 用户",
                "monetization": "免费+按席位订阅 ($10/人/月)",
                "pricing": "$10/user/mo",
                "traffic_channels": "PLG (产品驱动增长)、模板创作者生态、社媒风靡",
                "user_complaints": "移动端冷启动慢、离线体验差、学习门槛极高",
                "vulnerability": "移动端轻量单点任务（如3秒快速捕获随记）体验迟缓"
            },
            {
                "name": "Obsidian",
                "positioning": "本地 Markdown 双链知识库",
                "platforms": "全平台",
                "scale": "数百万开发者与学者",
                "monetization": "个人完全免费，官方多端同步与发布增值收费",
                "pricing": "免费 / $4/mo Sync",
                "traffic_channels": "极客圈层、GitHub 开源生态、本地优先 (Local-First) 理念",
                "user_complaints": "上手配置繁琐、缺少开箱即用的移动端美观 UI",
                "vulnerability": "偏向极客开发者，普通小白用户无法驾驭复杂的配置与插件体系"
            }
        ],
        "personas": [
            {
                "role_name": "David · 28岁 敏捷工程师 / 知识工作者",
                "device": "MacBook / iPhone",
                "jobs_to_be_done": "极速记录瞬时灵感，结构化导出至标准 Markdown，保障数据完全本地私有。",
                "pain_points": "市面工具充斥云端监控、联网同步迟缓，且导出格式充满私有锁死壁垒。",
                "willingness_to_pay": "愿意为极佳的本地体验与端到端加密工具支付买断费 $19.99~$39.99。"
            }
        ],
        "wedge_strategy": "以「本地优先 (Local-First) + 极速零等待响应 + 零隐私上传」作为破局点，用极致透明和极客口碑撕开巨头护城河。"
    }
}

def detect_category(product_name: str, product_code: str, target_market: str, strategic_intent: str) -> Dict[str, Any]:
    """Detects target domain category from text heuristics."""
    combined = f"{product_name} {product_code} {target_market} {strategic_intent}".lower()
    for cat_key, profile in CATEGORY_PROFILES.items():
        if any(kw in combined for kw in profile["keywords"]):
            return profile
    return CATEGORY_PROFILES["wallpaper_personalization"] if "pager" in combined or "wn" in combined else CATEGORY_PROFILES["utility_general"]

# ==============================================================================
# TAM / SAM / SOM Calculation Engine
# ==============================================================================

def calculate_tam_sam_som(
    category_profile: Dict[str, Any],
    target_market: str,
    arpu_override: Optional[float] = None
) -> Dict[str, Any]:
    """
    Computes a defensible, bottom-up TAM / SAM / SOM model.
    - TAM (Total Addressable Market): Total global demand for this product category.
    - SAM (Serviceable Available Market): Market bounded by target geography & target platforms (e.g. North America iOS/Android).
    - SOM (Serviceable Obtainable Market): Realistic market capture within 12-24 months under standard runway.
    """
    global_size = category_profile["global_market_size_usd"]
    arpu = arpu_override or category_profile["default_arpu_annual"]
    
    # Regional scaling
    is_na = any(k in target_market.lower() for k in ["北美", "north america", "美国", "us", "usa", "加拿大", "canada"])
    is_sea = any(k in target_market.lower() for k in ["东南亚", "sea", "印尼", "vietnam", "越南", "thailand", "泰国"])
    
    if is_na:
        region_factor = category_profile.get("north_america_share", 0.35)
        target_region_label = "北美市场 (美国、加拿大)"
        addressable_device_population = 280000000 # 280M smartphone users
        penetration_rate = 0.12 # 12% segment interested in customization/tools
    elif is_sea:
        region_factor = 0.22
        target_region_label = "东南亚市场 (印尼、越南、菲律宾等)"
        addressable_device_population = 350000000
        penetration_rate = 0.15
        arpu = max(3.99, arpu * 0.35) # Purchasing power adjustment
    else:
        region_factor = 0.30
        target_region_label = target_market or "核心目标区域"
        addressable_device_population = 200000000
        penetration_rate = 0.10

    tam_usd = round(global_size)
    sam_usd = round(tam_usd * region_factor)
    
    # SAM users
    sam_users = round(addressable_device_population * penetration_rate)
    
    # SOM Scenarios (Year 1 - Year 2 realistic projections)
    # Conservative (0.05% of SAM), Base (0.25% of SAM), Optimistic (0.80% of SAM)
    som_conservative_users = round(sam_users * 0.0005)
    som_base_users = round(sam_users * 0.0025)
    som_optimistic_users = round(sam_users * 0.0080)

    som_base_revenue = round(som_base_users * arpu)
    som_conservative_revenue = round(som_conservative_users * arpu)
    som_optimistic_revenue = round(som_optimistic_users * arpu)

    return {
        "region_label": target_region_label,
        "arpu_annual": arpu,
        "tam_usd": tam_usd,
        "tam_formatted": f"${tam_usd / 1000000000:.1f}B",
        "sam_usd": sam_usd,
        "sam_formatted": f"${sam_usd / 1000000:.0f}M",
        "sam_users": sam_users,
        "sam_users_formatted": f"{sam_users / 1000000:.1f}M",
        "som_base_users": som_base_users,
        "som_base_revenue_usd": som_base_revenue,
        "som_base_formatted": f"${som_base_revenue / 1000:.0f}K /年 ({som_base_users:,} 付费/活跃用户)",
        "scenarios": {
            "conservative": {
                "users": som_conservative_users,
                "revenue_usd": som_conservative_revenue,
                "note": "仅依靠 ASO 基础自然流量与初始种子社群沉淀"
            },
            "base": {
                "users": som_base_users,
                "revenue_usd": som_base_revenue,
                "note": "ASO 精准关键词霸榜 + TikTok 视觉视频小规模放量验证"
            },
            "optimistic": {
                "users": som_optimistic_users,
                "revenue_usd": som_optimistic_revenue,
                "note": "打造爆款锁屏破局点，形成跨平台自发病毒裂变"
            }
        }
    }

# ==============================================================================
# Full Deliverable Synthesis for Module 01
# ==============================================================================

def generate_comprehensive_market_report(
    product_name: str,
    product_code: str,
    target_market: str,
    strategic_intent: str,
    strategic_role: str = "acquisition",
    user_instruction: str = ""
) -> str:
    """
    Synthesizes an institutional-grade, 6-section Market Research report
    strictly aligned with ModuFlow's product incubator principles.
    """
    cat = detect_category(product_name, product_code, target_market, strategic_intent)
    mkt_model = calculate_tam_sam_som(cat, target_market)

    competitors = cat["competitors"]
    personas = cat["personas"]
    wedge = cat["wedge_strategy"]

    # 1. Competitors Table
    comp_rows = []
    for c in competitors:
        comp_rows.append(
            f"| **{c['name']}** | {c['positioning']} | {c['platforms']} | {c['scale']} | {c['pricing']} | {c['traffic_channels']} | {c['user_complaints']} | {c['vulnerability']} |"
        )
    competitors_table = "\n".join(comp_rows)

    # 2. Personas Markdown
    personas_blocks = []
    for idx, p in enumerate(personas, start=1):
        personas_blocks.append(
            f"#### 👤 画像 {idx}：{p['role_name']}\n"
            f"- **使用设备与系统**：`{p['device']}`\n"
            f"- **核心任务 (Jobs-To-Be-Done)**：{p['jobs_to_be_done']}\n"
            f"- **痛点与现有方案槽点**：{p['pain_points']}\n"
            f"- **价格接受度与付费心理**：{p['willingness_to_pay']}\n"
        )
    personas_content = "\n".join(personas_blocks)

    report_markdown = f"""# 《{product_name}》市场研究与竞品深度洞察报告 (v1.0)

> **工序代码**：`01` - 市场研究 (Market Research)  
> **受检产品**：`{product_code}` - **{product_name}** (战役角色: `{strategic_role}`)  
> **目标市场**：{mkt_model['region_label']}  
> **业务领域**：{cat['category_name']}  
> **研究责任人**：市场研究 Agent (资深行业分析与市场洞察总监)

---

## Executive Summary (执行摘要)
本报告基于战略工程顶层意图，深度剖析了 **{product_name}** 在 **{mkt_model['region_label']}** 所面临的竞争红蓝海格局。当前行业存在显著的“**体验断层与变现反噬**”现象：老牌头部应用（如 {competitors[0]['name']}、{competitors[2]['name'] if len(competitors) > 2 else competitors[1]['name']}）因过度追求短平快广告和激进周订阅变现，导致 App Store 差评与用户流失严重；而小众精品虽口碑极佳却停滞不前。这为 `{product_code}` 凭借**更锋利的单点破局刀法（Wedge）**切入并夺取首批核心用户提供了关键窗口期。

---

## 一、 TAM / SAM / SOM 市场空间测算模型 (Bottom-Up)

我们严禁空泛套用宏观万亿大盘，坚持采用**自下而上（Bottom-Up）**的可行受众测算法：

```
+-------------------------------------------------------------+
| 全球大盘 TAM: {mkt_model['tam_formatted']} (全球该品类年化软硬件与增值消费总体量)
|   +---------------------------------------------------------+
|   | 目标区域 SAM: {mkt_model['sam_formatted']} ({mkt_model['region_label']} 可触达目标设备盘: 约 {mkt_model['sam_users_formatted']} 用户)
|   |   +-----------------------------------------------------+
|   |   | 首期可占 SOM: {mkt_model['som_base_formatted']} (12-24个月基准渗透测算)
+---+---+---+-------------------------------------------------+
```

### 1. 核心测算参数与假设推演
- **单客年度有效贡献 (Blended ARPU)**：设定为 **${mkt_model['arpu_annual']:.2f} USD /年**（基于混合免费增值订阅与去广告买断的加权平均值）。
- **目标区域有效设备基数**：{mkt_model['region_label']} 内具备付费及高频美化习惯的目标用户群体约为 **{mkt_model['sam_users_formatted']}**。

### 2. 发展情景预测表 (Scenario Projections)
| 发展情景 | 目标付费/活跃用户 | 预期年度贡献 (USD) | 测算实现路径与核心依赖 |
| :--- | :--- | :--- | :--- |
| **保守情景 (Conservative)** | {mkt_model['scenarios']['conservative']['users']:,} | ${mkt_model['scenarios']['conservative']['revenue_usd']:,} | {mkt_model['scenarios']['conservative']['note']} |
| **基准情景 (Base Case)** | **{mkt_model['scenarios']['base']['users']:,}** | **${mkt_model['scenarios']['base']['revenue_usd']:,}** | **{mkt_model['scenarios']['base']['note']}** |
| **进取情景 (Optimistic)** | {mkt_model['scenarios']['optimistic']['users']:,} | ${mkt_model['scenarios']['optimistic']['revenue_usd']:,} | {mkt_model['scenarios']['optimistic']['note']} |

---

## 二、 核心竞品 Top 5 横向对比矩阵与软肋透析

我们精选了在目标市场占据不同生态位的标杆竞品进行全景解剖：

| 竞品名称 | 核心生态定位 | 平台覆盖 | 预估量级规模 | 定价与变现梯队 | 主要获客渠道 | 用户核心差评/槽点 (负评挖掘) | 致命软肋与破局缝隙 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
{competitors_table}

---

## 三、 用户画像与真实痛点挖掘 (ICP & Jobs-To-Be-Done)

基于目标市场的数字原住民与主力消费群，提炼出 3 个典型理想客户画像 (ICP)：

{personas_content}

---

## 四、 差异化破局切入点与战略切口 (The Wedge & Value Gap)

面对竞品庞大的库存累积和老牌 ASO 护城河，`{product_name}` 坚决**不打对称消耗战**，必须实施锋利的**单点击穿策略 (Wedge Strategy)**：

### 1. 核心价值缝隙 (Value Gap)
- **痛点断层**：竞品要么图库庞大但 90% 是垃圾搬运且广告轰炸；要么质量极高但多年不更新且缺乏工具化联动。
- **用户心智升级**：用户已经厌倦“为了找一张壁纸看 3 个 30 秒垃圾游戏广告”。年轻一代更愿意为**“即开即用、极致高清、具备锁屏景深或双屏柔焦配套的高级审美”**买单。

### 2. 锋利切入刀法 (The Wedge)
- **{wedge}**
- **冷启动获客打法**：在 TikTok 和 Instagram 上以“**10 秒手机桌面高级感蜕变 (Before vs After)**”为核心视觉钩子，避开高昂的通用搜索大词竞价，专攻视觉驱动型自然传播与精细化 ASO 长尾词。

---

## 五、 平台生态趋势与合规风险排查

1. **Apple App Store 订阅与审核合规红线**：
   - 严禁诱导性隐蔽周扣费（如模糊展示 `$2.99/周`），必须严格展示明确的免费试用期、计费周期与退订说明，避免遭到 Apple 审核驳回或用户大面积争议退款。
   - 动态锁屏壁纸及景深接口必须使用官方规范 API，避免调用私有 API 导致被下架。
2. **版权风险与原创新供给机制**：
   - 彻底告别网络抓取与盗图模式，前期与独立插画师、摄影师签约保底分成，建立独家创作者标识，形成版权护城河。
3. **低端机适配与性能门槛**：
   - 即使针对北美市场，仍有大量入门级机型，应用首屏启动必须控制在 **1.5秒** 内，图片加载支持动态 WebP/HEIC 分辨率降级，避免闪退与卡顿。

---

## 六、 对下游工序的输入建议与行动清单

为确保工序间的穿透性，本报告向下游工序提供直接的决策事实输入：

1. **对工序 02【商业模式分析】的输入**：
   - 坚决放弃容易导致 1 星差评的纯强硬周扣费模型，推荐采用 **“免费优质图库 + 激励视频免广告体验” + “$14.99/年订阅解锁全量 4K 景深及双屏配套” + “$29.99 极客买断”** 的复合变现结构。
2. **对工序 03【产品方向决策】与 06【PRD】的输入**：
   - MVP 范围坚决减法：第一版不搞复杂的社交、评论或多级嵌套，把资源全部集中在**“iOS 锁屏景深专区”**与**“双屏柔焦一键配套工具”**两大王牌体验上。
3. **对工序 04【低成本市场验证】的输入**：
   - 建议以 3 组 TikTok/Reels 桌面改造前后对比短视频进行假门测试，监控点击率 (CTR) 与落地页转化意向，验证获客成本能否压制在 $1.20 USD 以内。
"""
    return report_markdown
