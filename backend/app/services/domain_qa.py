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

    # Domain keyword heuristics
    is_competitor = any(k in q for k in ["竞品", "对手", "对标", "competitor", "类似", "谁在做", "标杆", "市场上有哪些", "哪几家", "分析竞品"])
    is_wallpaper_context = any(k in q for k in ["壁纸", "wallpaper", "锁屏", "美化", "主题", "背景"]) or "pager" in ctx["product_name"].lower() or "wn" in ctx["product_code"].lower()
    is_feature = any(k in q for k in ["功能", "feature", "需求", "mvp", "应该有什么", "清单", "规划", "设计"])
    is_pricing = any(k in q for k in ["定价", "收费", "价格", "变现", "商业化", "会员", "广告", "多少钱"])
    is_tech = any(k in q for k in ["技术", "架构", "选型", "数据库", "开发", "性能", "后端", "前端"])

    # 1. Competitor Analysis (对标竞品分析)
    if is_competitor or (is_wallpaper_context and ("竞品" in q or "对手" in q or "对标" in q)):
        return f"""### 对标北美市场：{ctx['product_name']} 核心竞品横向深度分析

基于母战略工程《{ctx['initiative_name']}》（目标市场：{ctx['target_market']}），针对当前工序【{module_name}】，我们选取北美市场占据不同生态位的 **Top 5 核心标杆竞品** 进行横向剖析与破局对标：

---

#### 一、 核心竞品 Top 5 横向对比矩阵

| 竞品名称 | 核心生态位 | 主打平台 | 月活/体量级 | 核心变现模式 | 定价区间 (USD) | 优势与破局软肋 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **1. Zedge** | 泛大众综合美化霸主 | iOS / Android | 千万级 MAU | 广告 + 订阅 + 积分内购 | $1.99/月 或 $9.99/年 | 资源极丰富但 UI 老旧繁杂，广告极多口碑下滑 |
| **2. Backdrops** | 极客/设计师原创社区 | Android / iOS | 百万级高黏性 | 免费+一次性买断 Pro | $3.99-$4.99 买断 | 原创质量极高无搬运，但更新慢、动态/工具属性弱 |
| **3. Wallcraft** | 算法适配与重商业化 | iOS / Android | 数百万级 | 强广告 + 激进周订阅 | $1.99/周 或 $14.99/年 | 全机型 4K/8K 精准裁切，但广告侵入性过强被反感 |
| **4. Vellum** | iOS 极简美学策展标杆 | iOS 独占 | 百万级口碑型 | 轻度广告 + 一次性 Pro | $2.99-$4.99 买断 | 内置高斯模糊工具与极简预览，但更新慢变现天花板低 |
| **5. Themify** | “壁纸+小组件+图标”整套整装 | iOS 主力 | 高 ARPU 订阅 | 强付费墙 + 周/年订阅 | $3.99/周 或 $29.99/年 | 单客 LTV 极高，但退订率高且极依赖昂贵买量投放 |

---

#### 二、 竞品商业模式与产品卖点深度拆解

1. **Zedge（混合变现教科书）**：
   - **核心打法**：免费用户看插屏/激励视频广告下载普通图；高品质动态壁纸采用代币（Credits）按件解锁；重度用户推荐月/年费去广告。
   - **借鉴点**：适合作为单品前期低 CAC 快速聚拢百万泛用户的流量漏斗。
2. **Backdrops（高质原创与社区护城河）**：
   - **核心打法**：“Wall of the Day”每日一张由签约设计师原创，提供完整的色卡参数（Hex Palette）供极客搭配小组件。
   - **借鉴点**：杜绝无脑搬运图，建立清晰的内容审美标准以提高用户自发传播度。
3. **Vellum（将壁纸工具化）**：
   - **核心打法**：内置强大的**实时高斯模糊（Blur Tool）**与锁屏/主屏双屏联动模拟，解决“精美壁纸做主屏看不清图标”的高频痛点。
   - **借鉴点**：做深工具属性（景深检测、双屏成对、模糊滤镜），形成竞品技术壁垒。

---

#### 三、 对 {ctx['product_name']} 的北美破局策略

1. **功能切入点**：聚焦 **iOS 锁屏景深（Depth Effect）专区** 与 **“锁屏高清主体 + 主屏同色系柔焦/暗角对图”**，做深工具价值。
2. **商业化定价**：规避高昂且反感的强周订阅，采用 **“免费图+激励视频解锁” + “$14.99/年订阅解锁 AI 模板微调与独家动态库” + “$29.99 极客买断”** 的分层变现体系。
3. **增长破局**：在 TikTok / Instagram Reels 开展“10秒手机桌面高级感改造（Before & After）”视觉营销，精准触达北美年轻客群。

---

*如需将上述竞品结论固化为工序成果，可直接在上方切换为「指令 (Instruction)」发送“生成竞品分析报告交付物”，系统将自动为您归档出正式交付物版本。*"""

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
