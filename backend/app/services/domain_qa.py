import re
from typing import Optional, Dict, Any

def extract_context_summary(system_context: str) -> Dict[str, str]:
    """Extract strategic initiative metadata from the markdown context file."""
    data = {
        "initiative_name": "当前出海母战略工程",
        "target_market": "目标细分市场",
        "business_model": "高频工具获客 + 增值变现闭环"
    }
    if not system_context:
        return data

    init_match = re.search(r"战略工程：([^\n]+)", system_context)
    if init_match:
        data["initiative_name"] = init_match.group(1).strip()

    market_match = re.search(r"目标市场：([^\n]+)", system_context)
    if market_match:
        data["target_market"] = market_match.group(1).strip()

    bm_match = re.search(r"商业模式假设：([^\n]+)", system_context)
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
    ctx = extract_context_summary(system_context)
    q = question.strip()

    # Domain keyword heuristics for tailored deep domain suggestions
    is_wallpaper = any(k in q for k in ["壁纸", "wallpaper", "锁屏", "美化", "主题"])
    is_pricing = any(k in q for k in ["定价", "收费", "价格", "变现", "商业化", "会员"])
    is_tech = any(k in q for k in ["技术", "架构", "选型", "数据库", "开发", "性能", "后端"])

    if is_wallpaper:
        body = f"""### 关于【壁纸类产品】核心功能规划与工序落地建议

基于母战略工程《{ctx['initiative_name']}》的顶层定性（目标市场：{ctx['target_market']}，商业逻辑：{ctx['business_model']}），当前工序【{module_name}】应重点规避“盲目堆砌功能”，围绕**低获客成本（CAC）、高使用频次与广告/订阅转化**搭建功能分级矩阵：

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
    elif is_pricing:
        body = f"""### 关于商业化与变现模式的推演建议

结合母战略工程《{ctx['initiative_name']}》的单位经济约束（{ctx['business_model']}）与工序【{module_name}】：

1. **变现模型选择**：
   - **混合变现 (Hybrid Monetization)**：基础功能完全免费降低摩擦以保障低 CAC 获客；高频界面接入轻度原生信息流广告；高阶功能提供无广告订阅（Weekly / Monthly VIP）。
   - **阶梯定价设计**：建议设置 3 天免费试用 + 周订阅（高周转冲冲抵投放成本）与年费终身买断（提供确定性现金流）。
2. **单位经济（Unit Economics）控制**：
   - 目标 LTV 必须覆盖买量成本与 CDN 存储开销，确保 LTV / CAC > 3.0。
3. **下一步行动**：
   - 可在工序内直接下发指令制定详细的收益测算模型与定价策略交付物。"""
    elif is_tech:
        body = f"""### 关于技术选型与架构设计的工序答复

结合母工程《{ctx['initiative_name']}》的技术规范与当前工序【{module_name}】：

1. **客户端与前端架构**：
   - 优先采用 Flutter / React Native 或原生轻量栈，保障秒开性能与全球化多端发布能力。
   - 关键指标：冷启动时间 < 800ms，安装包体积（APK/IPA）< 25MB 以降低海外弱网下载转化折损。
2. **CDN 与资源分发策略**：
   - 图片采用 WebP / AVIF 压缩格式，配合边缘 CDN 动态缩放切图，将单图网络流量降低 60% 以上。
3. **下一步行动**：
   - 可直接下发指令以本框架生成接口规范与可行性评估交付物。"""
    else:
        body = f"""### 关于您所提问题的工序分析答复

针对您在当前工序【{module_name}】提出的问题：**「{q}」**，结合母战略工程《{ctx['initiative_name']}》（目标市场：{ctx['target_market']}）的顶层定性：

1. **核心价值判断**：
   - 本工序需始终对齐战略底稿中的商业模式假设（{ctx['business_model']}），确保方案具备清晰的用户价值与商业闭环。
2. **关键维度推演**：
   - **用户端价值**：直接解决目标客群的核心痛点，降低交互链路认知负荷。
   - **业务端闭环**：形成明确的留存飞轮与变现抓手，杜绝不产生商业回报的边缘特性。
   - **上下游协同**：本工序的结论将作为下游工序（如设计、开发、测试）的刚性基线支撑。
3. **落地执行指引**：
   - 如需将本结论固化为工序成果，可切换上方为「指令 (Instruction)」并发送确认指令，系统将为您生成规范交付物。"""

    return body
