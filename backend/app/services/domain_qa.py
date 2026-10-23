import re
from typing import Optional, Dict, Any

def extract_context_summary(system_context: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    """Extract strategic initiative metadata from metadata dict or markdown context."""
    data = {
        "initiative_name": (metadata or {}).get("initiative_name") or "当前战略工程",
        "target_market": (metadata or {}).get("target_market") or "目标细分市场",
        "business_model": (metadata or {}).get("business_model_hypothesis") or "高频工具获客 + 增值变现闭环",
        "product_name": (metadata or {}).get("product_name") or "当前产品",
        "product_code": (metadata or {}).get("product_code") or ""
    }
    if not system_context:
        return data

    if data["initiative_name"] == "当前战略工程":
        init_match = re.search(r"(?:所属战略工程|战略工程)[*：:\s]+([^\n(`]+)", system_context)
        if init_match:
            data["initiative_name"] = init_match.group(1).strip()

    if data["target_market"] == "目标细分市场":
        market_match = re.search(r"(?:目标市场|Target Market)[*：:\s()]+([^\n]+)", system_context)
        if market_match:
            data["target_market"] = market_match.group(1).strip()

    if data["business_model"] == "高频工具获客 + 增值变现闭环":
        bm_match = re.search(r"(?:商业模式假设|Business Model Hypothesis)[*：:\s()]+([^\n]+)", system_context)
        if bm_match:
            data["business_model"] = bm_match.group(1).strip()

    return data

def generate_domain_qa_answer(
    question: str,
    module_name: str,
    system_context: str,
    metadata: Optional[Dict[str, Any]] = None
) -> str:
    """
    Synthesizes a high-fidelity, strategically-aligned answer for the human user's inquiry,
    grounded in the mother strategic initiative and the current workflow module baseline.
    """
    ctx = extract_context_summary(system_context, metadata)
    q = question.strip().lower()

    from backend.app.services.market_research_engine import (
        detect_category,
        calculate_tam_sam_som
    )

    cat = detect_category(ctx["product_name"], ctx["product_code"], ctx["target_market"], ctx["business_model"])

    # Domain keyword heuristics
    is_market_sizing = any(k in q for k in ["tam", "sam", "som", "市场规模", "市场容量", "大盘", "空间", "测算", "天花板", "体量", "年化", "产值", "空间有多大", "测算市场"])
    is_competitor = any(k in q for k in ["竞品", "对手", "对标", "competitor", "类似", "谁在做", "标杆", "市场上有哪些", "哪几家", "分析竞品", "优缺点", "优劣势", "差评", "zedge", "backdrops", "wallcraft", "vellum", "themify", "bukukas"])
    is_user_persona = any(k in q for k in ["用户", "画像", "persona", "icp", "痛点", "人群", "客群", "jtbd", "谁买单", "受众", "核心用户"])
    is_wedge = any(k in q for k in ["破局", "差异化", "切入点", "wedge", "切口", "核心卖点", "壁垒", "怎么打", "护城河", "如何竞争", "胜算", "价值缝隙"])
    is_compliance = any(k in q for k in ["合规", "政策", "审核", "风险", "apple", "google play", "下架", "抽成", "规则"])
    is_feature = any(k in q for k in ["功能", "feature", "需求", "mvp", "应该有什么", "清单", "规划", "设计"])
    is_pricing = any(k in q for k in ["定价", "收费", "价格", "变现", "商业化", "会员", "广告", "多少钱"])
    is_tech = any(k in q for k in ["技术", "架构", "选型", "数据库", "开发", "性能", "后端", "前端"])

    # 1. TAM / SAM / SOM Market Sizing (市场空间量化测算)
    if is_market_sizing:
        mkt = calculate_tam_sam_som(cat, ctx["target_market"])
        return f"""### 【市场研究 Agent】TAM / SAM / SOM 市场空间测算报告

基于母战略工程《{ctx['initiative_name']}》（目标市场：{ctx['target_market']}），本 Agent 采用**自下而上（Bottom-Up）的真实设备盘与加权 ARPU 测算模型**，严禁使用不可落地的空泛大盘数据：

---

#### 1. 核心测算参数与三层空间模型
```
+-------------------------------------------------------------+
| 全球大盘 TAM: {mkt['tam_formatted']} (全球该品类数字化总体量)
|   +---------------------------------------------------------+
|   | 目标区域 SAM: {mkt['sam_formatted']} ({mkt['region_label']} 可触达目标设备: 约 {mkt['sam_users_formatted']} 用户)
|   |   +-----------------------------------------------------+
|   |   | 首期可占 SOM: {mkt['som_base_formatted']} (12-24个月基准渗透测算)
+---+---+---+-------------------------------------------------+
```
- **单客年度有效加权价值 (Blended ARPU)**：设为 **${mkt['arpu_annual']:.2f} USD /年**（综合了免费广告、按件内购、年度 VIP 订阅与买断的加权平均值）。
- **目标区域有效设备基数 (SAM)**：{mkt['region_label']} 内对【{cat['category_name']}】具备明确使用习惯的用户基数约为 **{mkt['sam_users_formatted']}**，潜在可触达年化盘为 **{mkt['sam_formatted']}**。

---

#### 2. 三套发展情景模拟 (Scenario Modeling)
| 情景假设 | 12-24月目标用户 | 年化营收预测 (USD) | 测算实现路径与依赖条件 |
| :--- | :--- | :--- | :--- |
| **保守情景 (Conservative)** | {mkt['scenarios']['conservative']['users']:,} | ${mkt['scenarios']['conservative']['revenue_usd']:,} | {mkt['scenarios']['conservative']['note']} |
| **基准情景 (Base Case)** | **{mkt['scenarios']['base']['users']:,}** | **${mkt['scenarios']['base']['revenue_usd']:,}** | **{mkt['scenarios']['base']['note']}** |
| **乐观情景 (Optimistic)** | {mkt['scenarios']['optimistic']['users']:,} | ${mkt['scenarios']['optimistic']['revenue_usd']:,} | {mkt['scenarios']['optimistic']['note']} |

---

#### 3. 市场研究 Agent 建议
对「{ctx['product_name']}」而言，在首期迭代中不必盲目追求全球通吃，把资源集中在 **{mkt['region_label']}** 验证 **${mkt['som_base_revenue_usd'] / 1000:.0f}K /年** 的基准单元经济模型，是实现正向现金流的最稳健路径。
*如需固化为工序正式成果，请切换为「指令」发送“生成市场研究交付物”。*"""

    # 2. Value Gap & Wedge Strategy (破局切口与差异化战法，优先于泛竞品提问)
    if is_wedge:
        return f"""### 【市场研究 Agent】{ctx['product_name']} 差异化破局切入点与战略切口 (The Wedge)

在成熟市场对抗老牌巨头，必须严格规避正面对称战，实施**以点带面的单点击穿策略 (Wedge Strategy)**：

---

#### 1. 核心价值缝隙 (The Value Gap)
- 老牌大厂受制于上市财报压力，必须持续压榨广告位和激进周订阅以维持流水，导致留存断崖式下跌。
- 极客团队产品多年不更新，无法适配最新一代手机的锁屏与交互新特性。
- **缝隙就在于：以工具化思维提供高审美配套，打造无广告或轻度克制的高清体验**。

#### 2. 锋利切入刀法 (The Wedge Strategy)
- **破局功能单点**：{cat['wedge_strategy']}
- **前 10,000 冷启动打法**：
  - 规避竞价昂贵的通用大词广告投放；
  - 聚焦 TikTok / Instagram 上的桌面美化短视频，以 **“10秒桌面高级感改造 (Before vs After)”** 为视觉钩子，引流至 App Store 落地页；
  - 通过极客社区（Reddit r/iOSsetups 等）沉淀第一批高黏性意见领袖。"""

    # 3. User Personas & ICP / JTBD (用户画像与真实痛点挖掘)
    if is_user_persona:
        personas = cat["personas"]
        p_blocks = []
        for idx, p in enumerate(personas, start=1):
            p_blocks.append(
                f"#### 👤 画像 {idx}：{p['role_name']}\n"
                f"- **使用设备与偏好**：`{p['device']}`\n"
                f"- **核心任务 (Jobs-To-Be-Done)**：{p['jobs_to_be_done']}\n"
                f"- **未满足痛点与吐槽**：{p['pain_points']}\n"
                f"- **价格接受度与付费心理**：{p['willingness_to_pay']}\n"
            )
        p_content = "\n".join(p_blocks)

        return f"""### 【市场研究 Agent】{ctx['product_name']} 目标用户画像 (ICP) 与真实痛点挖掘

针对目标市场【{ctx['target_market']}】，我们提炼了 3 个高价值典型用户画像及其核心 Jobs-To-Be-Done：

---

{p_content}

---

#### 核心用户痛点共性归纳：
1. **现有产品要么太烂（广告满天飞），要么太贵（被强行周订阅吸血）**。
2. **缺乏针对现代系统（如 iOS 景深、双屏成对）的深度工具化支持**。
3. **年轻代高净值用户渴望表达个性，愿意为极高审美和干净体验买单**。"""

    # 4. Competitor Analysis & 1-Star Review Mining (对标竞品横向分析与负评挖掘)
    if is_competitor:
        competitors = cat["competitors"]
        comp_rows = []
        for c in competitors:
            comp_rows.append(
                f"| **{c['name']}** | {c['positioning']} | {c['scale']} | {c['pricing']} | {c['user_complaints']} | {c['vulnerability']} |"
            )
        comp_table = "\n".join(comp_rows)

        return f"""### 【市场研究 Agent】{ctx['product_name']} 核心标杆竞品横向对比与负评深度拆解

针对目标市场【{ctx['target_market']}】，我们选取当前生态位占据不同梯队的 **Top 标杆竞品**，重点拆解其**商业模式、用户高频槽点（1-2 星差评挖掘）与防守软肋**：

---

#### 一、 核心竞品横向对比矩阵

| 竞品名称 | 核心生态定位 | 预估量级规模 | 定价与变现梯队 | App Store 1-2 星核心差评与槽点 | 致命软肋与破局缝隙 |
| :--- | :--- | :--- | :--- | :--- | :--- |
{comp_table}

---

#### 二、 竞品负面槽点归因与破局缝隙 (Where They Fail)
1. **强行周扣费与退订陷阱引爆反感**：
   - 诸如 Wallcraft、Themify 等应用通过暗扣周费（$1.99~$4.99/周）赚取暴利，但导致 App Store 评分暴跌至 2 星区间，大面积用户寻求退款。
   - **破局切入**：坚持**清爽、透明的商业化定价**（免费优质基础体验 + 年费订阅 + 买断制），建立健康的品牌信任资产。
2. **重度侵扰式广告毁灭体验**：
   - 泛大众老牌应用每次下载看 30 秒无法跳过的低俗弹窗广告，严重侵蚀核心年轻用户体验。
   - **破局切入**：主打极简工具化与高审美原创，拒绝低劣侵入式插屏，利用高口碑形成低 CAC 增长自留地。

---

*如需将上述竞品结论固化为工序成果，可直接切换为「指令 (Instruction)」发送“生成竞品分析报告交付物”。*"""

    # 5. Policy & Platform Compliance (平台政策与合规风险)
    if is_compliance:
        return f"""### 【市场研究 Agent】平台合规红线与生态政策评估

针对出海及主流应用分发平台（Apple App Store / Google Play），梳理当前核心合规要求与避坑指南：

1. **Apple App Store 订阅合规要求**：
   - 严禁隐瞒扣费金额，购买页必须用醒目字号标注订阅价格、自动续期机制以及取消订阅路径。
   - 如果提供免费试用（Free Trial），必须明确告知试用结束后将自动按指定价格扣费。
2. **内容版权与原创新供给机制**：
   - 彻底规避未经授权的网络批量爬取图片，避免收到 DMCA 侵权投诉导致账号受限。
   - 建立原创签约画师分成或免版权开源高清图库筛选机制。
3. **隐私安全与 ATT (App Tracking Transparency)**：
   - 严格遵循 iOS 隐私追踪合规，若接入三方广告 SDK，必须合规弹窗征求用户授权，不得在用户拒绝后继续通过指纹识别跨应用追踪。"""

    # 6. Features & Functional Hierarchy (功能规划与清单)
    if is_feature:
        return f"""### 关于【{ctx['product_name']}】核心功能规划与工序落地建议

基于母战略工程《{ctx['initiative_name']}》（目标市场：{ctx['target_market']}，商业逻辑：{ctx['business_model']}），当前工序【{module_name}】应重点规避“盲目堆砌功能”，围绕**低获客成本（CAC）、高使用频次与转化**搭建功能分级矩阵：

---

#### 1. P0 必备核心（MVP 必保基线）
- **高清晰度图库与精细分类**：4K/极简/插画等标签化导航，支持无限瀑布流与弱网秒级预加载。
- **所见即所得双屏预览**：一键模拟主屏（带图标）与锁屏（带时钟部件）的实机效果。
- **原生一键设为壁纸**：支持单独设置主屏、锁屏或双屏同步，自动按设备屏幕比例裁剪居中。
- **轻量本地缓存**：离线状态下可秒开已浏览资源。

#### 2. P1 差异化与活跃黏性（破局飞轮关键）
- **壁纸自动轮换服务 (Auto-Changer)**：支持设定每日或解锁时自动轮换。
- **视差与景深适配 (Depth Effect)**：支持针对 iOS 锁屏主体进行景深与时钟联动展示。
- **双屏柔焦配套工具箱 (Dual Pair)**：锁屏高清主体，主屏一键同色系高斯模糊，解决图标杂乱问题。

#### 3. P2 商业化与高价值增值点
- **VIP 专属画师独家内容库**：看激励视频解锁或年度订阅解锁。
- **AI 智能微调与扩图**：微调色彩与暗黑模式适配。

---

*若确认以上分级方向，请在当前工序切换为「指令」发送“生成交付物”，系统将自动为您生成正式规范。*"""

    # 7. Pricing & Monetization (定价与商业化)
    elif is_pricing:
        return f"""### 关于 {ctx['product_name']} 商业化与变现模式的推演建议

结合母战略工程《{ctx['initiative_name']}》的单位经济约束（{ctx['business_model']}）与工序【{module_name}】：

1. **变现模型选择**：
   - **混合变现 (Hybrid Monetization)**：基础内容免费或通过看激励视频下载，以极低摩擦保障低 CAC 获客；高频界面接入轻度原生信息流；高阶功能提供无广告订阅。
   - **阶梯定价设计**：建议设置 3 天免费试用 + $1.99/周 或 $14.99/年，并提供 $29.99 终身买断（迎合极客客群并带来确定性预付现金流）。
2. **单位经济（Unit Economics）控制**：
   - 目标 LTV 必须覆盖买量成本与存储 CDN 开销，确保 LTV / CAC > 3.0。"""

    # 8. Tech & Architecture (技术与可行性)
    elif is_tech:
        return f"""### 关于 {ctx['product_name']} 技术选型与架构设计的工序答复

结合母工程《{ctx['initiative_name']}》的技术规范与当前工序【{module_name}】：

1. **客户端架构**：
   - 优先采用轻量跨平台（Flutter / React Native）或原生栈，保障启动秒开能力。
   - 关键指标：冷启动时间 < 800ms，安装包体积（APK/IPA）< 25MB 以降低海外下载转化折损。
2. **CDN 与资源分发策略**：
   - 图片采用 WebP / AVIF 现代压缩格式，配合边缘 CDN 动态缩放切图，将单图流量消耗降低 60% 以上。"""

    # 9. Default General Strategic Fallback
    else:
        return f"""### 关于您所提问题的工序分析答复

针对您在当前工序【{module_name}】提出的问题：**「{question.strip()}」**，结合母战略工程《{ctx['initiative_name']}》（目标市场：{ctx['target_market']}）的顶层定性：

1. **核心价值判断**：
   - 本工序需始终对齐战略底稿中的商业模式假设（{ctx['business_model']}），确保方案具备清晰的用户价值与商业闭环。
2. **关键维度推演**：
   - **用户端价值**：针对「{ctx['product_name']}」的目标客群痛点展开设计，降低认知负荷。
   - **业务端闭环**：形成明确的留存飞轮与变现抓手，杜绝不产生商业回报的边缘特性。
   - **上下游协同**：本工序的结论将作为下游工序（如商业模式、产品方向、开发测试）的坚实基线支撑。
3. **落地执行指引**：
   - 如需将本结论固化为工序成果，可切换上方为「指令 (Instruction)」并发送确认指令，系统将为您生成规范交付物。"""


    # 2. Features & Functional Hierarchy (功能规划与清单)
    if is_feature or (is_wallpaper_context and not (is_pricing or is_tech)):
        return f"""### 关于【{ctx['product_name']} 壁纸应用】核心功能规划与工序落地建议

基于母战略工程《{ctx['initiative_name']}》（目标市场：{ctx['target_market']}，商业逻辑：{ctx['business_model']}），当前工序【{module_name}】应重点规避“盲目堆砌功能”，围绕**低获客成本（CAC）、高使用频次与广告/订阅转化**搭建功能分级矩阵：

---

#### 1. P0 必备核心（MVP 必保基线）
- **高清晰度图库与精细分类**：4K/AMOLED/极简/插画等标签化导航，支持无限瀑布流与弱网秒级预加载。
- **所见即所得双屏预览**：一键模拟主屏（带图标、Dock栏）与锁屏（带时钟、通知部件）的实机效果。
- **原生一键设为壁纸**：支持单独设置主屏、锁屏或双屏同步，自动按设备屏幕物理比例裁剪居中。
- **基础收藏与轻量本地缓存**：允许用户收藏心仪壁纸，离线状态下可快速二次查看，节省重复流量开销。

#### 2. P1 差异化与活跃黏性（商业飞轮关键）
- **壁纸自动轮换服务 (Auto-Changer)**：支持设定频率（如每日一换、解锁屏幕时更换）与轮换分类池，将一次性低频设置转化为每日无感打开的高留存入口。
- **动效与视差壁纸 (Live / Parallax Wallpapers)**：陀螺仪重力感应视差深度壁纸、轻量 MP4/WebM 动态壁纸（需对耗电量与发热做严格把控）。
- **个性化编辑与调色工具箱**：支持用户添加毛玻璃模糊 (Blur Effect)、轻度滤镜、暗色模式适配蒙层，满足自制壁纸需求。

#### 3. P2 商业化与高价值增值点
- **VIP 专属画师独家内容库**：设置免费看激励视频广告解锁、或订阅 VIP 会员解锁 8K/动态独家专区。
- **AI 智能生图与扩图 (AI Wallpaper Generator)**：输入关键词或风格即可生成专属手机壁纸，提供每日免费额度 + 积分充值消耗。
- **UGC 创作者社区与分成激励**：允许签约画师与高质量用户上传壁纸，形成自繁殖内容供给飞轮。

---

#### 【工序推进建议】
若确认以上分级方向，请在当前工序下达指令（如输入：*“请将上述 P0/P1 功能梳理为正式工序交付物”*），我将自动为您生成或修订规范文档初稿。"""

    # 3. Pricing & Monetization (定价与商业化)
    elif is_pricing:
        return f"""### 关于 {ctx['product_name']} 商业化与变现模式的推演建议

结合母战略工程《{ctx['initiative_name']}》的单位经济约束（{ctx['business_model']}）与工序【{module_name}】：

1. **变现模型选择**：
   - **混合变现 (Hybrid Monetization)**：基础静态壁纸完全免费或看激励视频下载，以极低摩擦保障低 CAC 获客；高频界面接入轻度原生信息流广告；高阶功能提供无广告订阅（Weekly / Annual VIP）。
   - **阶梯定价设计**：建议设置 3 天免费试用 + $1.99/周 或 $14.99/年（高转化冲抵投放成本），并提供 $29.99 终身买断（迎合北美极客并带来确定性现金流）。
2. **单位经济（Unit Economics）控制**：
   - 目标 LTV 必须覆盖买量成本与 CDN 存储开销，确保 LTV / CAC > 3.0。
3. **下一步行动**：
   - 可在工序内直接下发指令制定详细的收益测算模型与定价策略交付物。"""

    # 4. Tech & Architecture (技术与可行性)
    elif is_tech:
        return f"""### 关于 {ctx['product_name']} 技术选型与架构设计的工序答复

结合母工程《{ctx['initiative_name']}》的技术规范与当前工序【{module_name}】：

1. **客户端与前端架构**：
   - 优先采用 Flutter / React Native 或原生轻量栈，保障秒开性能与全球化多端发布能力。
   - 关键指标：冷启动时间 < 800ms，安装包体积（APK/IPA）< 25MB 以降低海外弱网下载转化折损。
2. **CDN 与资源分发策略**：
   - 图片采用 WebP / AVIF 压缩格式，配合边缘 CDN 动态缩放切图，将单图网络流量降低 60% 以上。
3. **下一步行动**：
   - 可直接下发指令以本框架生成接口规范与可行性评估交付物。"""

    # 5. Default General Strategic Fallback
    else:
        return f"""### 关于您所提问题的工序分析答复

针对您在当前工序【{module_name}】提出的问题：**「{question.strip()}」**，结合母战略工程《{ctx['initiative_name']}》（目标市场：{ctx['target_market']}）的顶层定性：

1. **核心价值判断**：
   - 本工序需始终对齐战略底稿中的商业模式假设（{ctx['business_model']}），确保方案具备清晰的用户价值与商业闭环。
2. **关键维度推演**：
   - **用户端价值**：针对「{ctx['product_name']}」的目标客群痛点展开设计，降低交互链路认知负荷。
   - **业务端闭环**：形成明确的留存飞轮与变现抓手，杜绝不产生商业回报的边缘特性。
   - **上下游协同**：本工序的结论将作为下游工序（如设计、开发、测试）的刚性基线支撑。
3. **落地执行指引**：
   - 如需将本结论固化为工序成果，可切换上方为「指令 (Instruction)」并发送确认指令，系统将为您生成规范交付物。"""
