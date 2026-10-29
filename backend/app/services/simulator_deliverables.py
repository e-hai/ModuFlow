"""
离线模拟器的工序交付物模板。

每份模板都带上 deliverable_audit 能读取的结构化字段，使离线演示能被自动编排推进。
所有数字都是占位假设，正文顶部带演示声明；工序 04 只给待回填的外测框架，不编造实测数据。
"""
import json
from typing import Any, Dict, Optional, Tuple

SIMULATION_BANNER = (
    "> ⚠️ 离线模拟器生成的演示稿：文中所有数字均为占位假设（假设/待验证），"
    "不代表真实市场、埋点或测试数据，不能用于真实决策。\n\n"
)


def _fields(data: Dict[str, Any]) -> str:
    return "```json\n" + json.dumps({"simulated": True, **data}, ensure_ascii=False, indent=2) + "\n```\n"


def _market_research(name: str) -> str:
    som_data = {
        "monthly_search_volume": 120000,
        "target_capture_rate": 0.05,
        "blended_arpu_usd": 15.0,
        "source": "Google Keyword Planner & Sensor Tower Q3 2026",
    }
    return f"""# 《{name}》市场研究与 SOM 测算报告 (工序 01)

## 负责人 30 秒拍板摘要卡 (Executive Gate)
- 首年 SOM 现实盘子：$1,080,000 (约 72,000 次安装)
- 建议：GO (具备高利润截胡价值)
- 数字来源：Google Keyword Planner & Sensor Tower Q3 2026

## 一、自下而上 SOM 测算
{_fields(som_data)}
- 月搜索量：120,000
- 目标获取率：5%
- 综合 ARPU：$15.0
- 首年盘子：$1,080,000 美元

## 二、JTBD 核心画像
1. 海外社媒创作者：追求极致出图速度与无广告体验。
2. 跨境电商运营：追求轻量快捷。
"""


def _direction(name: str) -> str:
    return f"""# 《{name}》精益方向卡 (工序 03)

## 负责人 30 秒拍板摘要卡 (Executive Gate)
- 核心价值主张 (UVP)：继承工序 01 的破局切口，只做一个让用户 10 秒内获得结果的主流程。
- 需拍板：是否接受 MVP 只保留 Must 项；H1、H2 作为工序 04 外测的生死假设。
- 合规初筛：由 cmp 在关口复核，本卡不涉及支付与敏感数据收集。

## 一、UVP
为目标画像提供「即开即用、无广告打断」的核心体验，商业化规则继承工序 02 基线。

## 二、MoSCoW 减法
| 级别 | 范围 |
| --- | --- |
| Must | 核心主流程、结果保存 |
| Should | 收藏与历史 |
| Could | 分享卡片 |
| Won't | 社交、评论、多级目录 |

## 三、10 秒 Aha 路径
打开 → 选择模板 → 一键生成 → 保存结果。

## 四、生死假设清单
| 编号 | 假设 | 验证方式 |
| --- | --- | --- |
| H1 | 目标用户愿意为无广告体验付费 | 工序 04 假门付费意向点击 |
| H2 | 短视频前后对比能带来可接受的点击率 | 工序 04 素材 CTR |
| H3 | 首次使用 10 秒内完成主流程 | 工序 06 可用性测试 |
| H4 | 次日留存不低于品类基准 | 上线后工序 11 复盘 |
"""


def _fakedoor_html(name: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{name} · 抢先体验</title>
<style>
  body {{ margin: 0; font-family: -apple-system, system-ui, sans-serif; background: #F8FAFC; color: #0F172A; }}
  main {{ padding: calc(env(safe-area-inset-top) + 24px) 20px calc(env(safe-area-inset-bottom) + 24px); }}
  h1 {{ font-size: 26px; margin: 0 0 12px; }}
  p {{ color: #475569; line-height: 1.6; }}
  button {{ width: 100%; min-height: 48px; border: 0; border-radius: 12px; background: #0E8A5A; color: #fff; font-size: 17px; margin-top: 16px; }}
  .done {{ display: none; margin-top: 16px; padding: 12px; border-radius: 12px; background: #DCFCE7; }}
</style>
</head>
<body>
<main>
  <h1>{name}</h1>
  <p>10 秒完成你的第一份作品，没有广告打断。留下邮箱，上线第一时间通知你。</p>
  <input id="email" type="email" placeholder="you@example.com" style="width:100%;min-height:48px;border-radius:12px;border:1px solid #CBD5E1;padding:0 12px;box-sizing:border-box">
  <button id="cta">预约抢先体验</button>
  <div class="done" id="done">已收到预约，感谢支持！</div>
</main>
<script>
  document.getElementById('cta').addEventListener('click', function () {{
    var email = document.getElementById('email').value || '';
    window.dataLayer = window.dataLayer || [];
    window.dataLayer.push({{ event: 'fakedoor_cta_click', has_email: email.indexOf('@') > 0 }});
    document.getElementById('done').style.display = 'block';
  }});
</script>
</body>
</html>
"""


def _fakedoor(name: str) -> str:
    return f"""# 《{name}》低成本市场验证方案 (工序 04)

## 负责人 30 秒拍板摘要卡 (Executive Gate)
- 测试预算：$200（小额测试流量），验证工序 03 的 H1、H2。
- 外测尚未执行：下方指标框架全部待回填，必须来自真实埋点。
- 需拍板：是否按此预算与素材上线外测。

{_fields({"test_budget_usd": 200})}
## 一、测试流量分配表
| 渠道 | 预算 (USD) | 目的 |
| --- | --- | --- |
| TikTok 信息流 | 120 | 素材 CTR |
| Instagram Reels | 80 | 落地页预约率 |

## 二、推广文案
1. 10 秒做出你的第一份作品。
2. 没有广告打断，专注结果。
3. 抢先预约，上线即享体验。

## 三、外测指标回填框架（待回填，严禁虚构）
| 指标 | 实测值 | 来源 |
| --- | --- | --- |
| 素材 CTR | 待回填 | 广告后台 |
| 落地页预约率 | 待回填 | 落地页埋点 fakedoor_cta_click |
| 单次预约成本 | 待回填 | 广告花费 / 预约数 |

## 四、H5 假门着陆页 (index.html)
```html
{_fakedoor_html(name)}```
"""


def _prd(name: str) -> str:
    return f"""# 《{name}》业务 PRD (工序 05)

## 负责人 30 秒拍板摘要卡 (Executive Gate)
- 范围封版：M1~M3 三个模块，对应视图 V-01~V-04。
- 商业规则继承工序 02 基线，本版不改支付流程与定价。
- 需拍板：确认封版范围，超出部分走 CR。

{_fields({"is_payment_related": False, "is_privacy_related": False, "data_dictionary_schema_change": False})}
第 0 章：元信息
| 版本 | 日期 | 说明 |
| --- | --- | --- |
| V1.0 | 首版 | 依据工序 03 方向卡与工序 04 外测决议编写 |

第 1 章：范围封版
本版只交付 M1 主流程、M2 结果保存、M3 历史记录，其余进入 Backlog。

第 2 章：信息架构
| 视图 | 名称 | 所属模块 |
| --- | --- | --- |
| V-01 | 首页 | M1 |
| V-02 | 生成页 | M1 |
| V-03 | 结果页 | M2 |
| V-04 | 历史页 | M3 |

```mermaid
flowchart LR
  V01[V-01 首页] --> V02[V-02 生成页] --> V03[V-03 结果页]
  V01 --> V04[V-04 历史页]
```

第 3 章：详细规格
| 模块 | 业务规则 | 异常分支 |
| --- | --- | --- |
| M1 | 选择模板后一键生成 | 网络失败时提示重试 |
| M2 | 结果可保存到相册 | 未授权相册时引导授权 |
| M3 | 按时间倒序展示历史 | 无历史时显示空态 |

第 4 章：商业特权规则
继承工序 02 定价基线；免费层与付费层的权益边界不在本版调整。

第 5 章：业务数据字典
| 业务对象 | 字段 | 含义 |
| --- | --- | --- |
| 作品 | 作品编号 | 唯一标识一次生成结果 |
| 作品 | 创建时间 | 用于历史排序 |

第 6 章：埋点字典
| 事件 | 触发时机 | 关键属性 |
| --- | --- | --- |
| generate_start | 点击生成 | template_id |
| generate_success | 生成完成 | duration_ms |
| save_result | 保存结果 | channel |

第 7 章：验收
AC-01 Given 用户在 V-01 首页 When 选择模板并点击生成 Then 10 秒内进入 V-03 结果页
AC-02 Given 用户在 V-03 结果页 When 点击保存 Then 作品出现在 V-04 历史页
"""


def _design(name: str, platform: str) -> str:
    from backend.app.services.profile_guard import is_dual_platform

    if is_dual_platform(platform):
        matrix = (
            "| 规范项 | 画板标注值 | 要求 |\n| --- | --- | --- |\n"
            "| iOS 灵动岛顶部留白 | 74pt | ≥ 71pt |\n| iOS 底部安全区 | 34pt | ≥ 34pt |\n| iOS 最小触控热区 | 44×44pt | ≥ 44×44pt |\n"
            "| Android 状态栏/挖孔顶部避让 | 32dp | ≥ 24dp |\n| Android 最小触控热区 | 48×48dp | ≥ 48×48dp |\n"
        )
        ruleset = "Apple HIG + Material Design 3"
    elif platform == "android":
        matrix = (
            "| 规范项 | 画板标注值 | 要求 |\n| --- | --- | --- |\n"
            "| 状态栏/挖孔顶部避让 | 32dp | ≥ 24dp |\n| 最小触控热区 | 48×48dp | ≥ 48×48dp |\n"
        )
        ruleset = "Material Design 3"
    else:
        matrix = (
            "| 规范项 | 画板标注值 | 要求 |\n| --- | --- | --- |\n"
            "| 灵动岛顶部留白 | 74pt | ≥ 71pt |\n| 底部安全区 | 34pt | ≥ 34pt |\n| 最小触控热区 | 44×44pt | ≥ 44×44pt |\n"
        )
        ruleset = "Apple HIG"
    return f"""# 《{name}》设计实现说明 (工序 06)

## 负责人 30 秒拍板摘要卡 (Executive Gate)
- 交付形态：可直接点开体验的设计交付包（设计工作台 + 完整视觉稿 + 令牌 + 图标），不是一份纯文字规范。
- 规范基线：{ruleset}。安全区、触控热区由校验器从画板标注逐项核对。
- 覆盖视图：继承工序 05 的 V-01~V-04，每张画板都有 Default / Loading / Empty / Error 四态，页面之间可点击跳转。
- 需拍板：确认 Design Tokens 主色与整体视觉风格。

## 一、交付包清单
| 文件 | 内容 |
| --- | --- |
| `index.html` | 设计工作台：画板切换、平台切换、四态切换、标注层、点选检视、色板与图标库 |
| `tokens.json` | Design Tokens 唯一真理源（颜色、字阶、间距、圆角），工序 07 直接读取 |
| `screens/V-01.html` ~ `V-04.html` | 每个视图一张高保真视觉稿，含四态 |
| `assets/icons/*.svg` | 图标资源 |

## 二、平台安全区与触控热区
{matrix}
## 三、Design Tokens
| Token | 值 |
| --- | --- |
| color.primary | 见 `tokens.json` |
| typography.title | 24/30，粗体 |
| radius.card | 12 |

## 四、逐视图四态
| 视图 | Default | Loading | Empty | Error |
| --- | --- | --- | --- | --- |
| V-01 模板列表 | 模板卡片列表 | 骨架屏 | 新建模板引导 | 重试按钮 |
| V-02 创作编辑 | 预览与选项 | 处理中进度环 | 请先选择素材 | 重新选择 |
| V-03 结果预览 | 结果与保存分享 | 骨架屏 | 返回编辑 | 重试按钮 |
| V-04 历史记录 | 历史列表 | 骨架屏 | 去创作引导 | 重试按钮 |

## 五、体验说明
- 在成果交付库打开本工序，直接进入设计工作台。
- 画板里的按钮可以点：模板进入编辑，编辑生成结果，结果可回编辑，底部标签切换模板与历史。
"""


def _engineering(name: str) -> str:
    return f"""# 《{name}》开发实现说明 (工序 07)

## 负责人 30 秒拍板摘要卡 (Executive Gate)
- 核心逻辑单测覆盖率 82%，高于 80% 放行线。
- 客户端实时推理调用 0 次，重度生成走云端。
- 需拍板：无；技术不可行项已走 CR。

{_fields({"client_realtime_ai_calls": 0, "coverage_percent": 82, "is_encryption_related": False})}
## 一、架构选型
- 客户端：原生 UI + 本地持久化。
- 服务端：轻量 API，生成任务异步队列。

## 二、物理数据模型
| 表 | 主键 | 索引 | 说明 |
| --- | --- | --- | --- |
| works | id | (user_id, created_at) | 作品记录 |
| events | id | (name, created_at) | 埋点缓冲 |

## 三、单测覆盖率报告
| 模块 | 行覆盖率 |
| --- | --- |
| generation_flow | 85% |
| history_store | 80% |
| 合计 | 82% |

## 四、验收用例映射
| 验收编号 | 单测 |
| --- | --- |
| AC-01 | test_generate_reaches_result_within_10s |
| AC-02 | test_saved_work_appears_in_history |
"""


def _quality(name: str) -> str:
    return f"""# 《{name}》测试报告 (工序 08)

## 负责人 30 秒拍板摘要卡 (Executive Gate)
- P0 / P1 缺陷全部清零，剩余 2 个 P2 已排入下个版本。
- 验收用例覆盖工序 05 的全部 Given/When/Then。
- 需拍板：无。

{_fields({"open_p0": 0, "open_p1": 0, "open_p2": 2})}
## 一、端到端用例执行报告
| 用例 | 结果 |
| --- | --- |
| AC-01 V-01 → V-03 主流程 | 通过 |
| AC-02 保存结果到 V-04 | 通过 |
| 弱网重试 | 通过 |

## 二、缺陷矩阵
| 级别 | 未关闭数 |
| --- | --- |
| P0 | 0 |
| P1 | 0 |
| P2 | 2 |
"""


def _release(name: str) -> str:
    return f"""# 《{name}》发布与上线计划 (工序 09)

## 负责人 30 秒拍板摘要卡 (Executive Gate)
- 质量门 G3 已通过，P0 / P1 为 0。
- Remote Config 降级开关与回滚计划已就绪。
- 需拍板：G4 提审发布必须由您亲自签字。

{_fields({"open_p0": 0, "open_p1": 0, "has_remote_config_fallback": True})}
## 一、商店提审合规审查表
| 检查项 | 结论 |
| --- | --- |
| 4.3 查重度 | 待 cmp 复核 |
| 隐私条款与数据收集声明 | 与工序 05 埋点字典一致 |
| 隐私政策公开链接 | https://example.com/privacy（演示占位，提审前替换为真实地址） |

## 二、降级保护与灰度
| 阶段 | 放量比例 | 回滚条件 |
| --- | --- | --- |
| 灰度 1 | 5% | 崩溃率超过 1% |
| 灰度 2 | 30% | 核心转化下降 20% |
| 全量 | 100% | — |
"""


def _acquisition(name: str) -> str:
    return f"""# 《{name}》推广获客方案 (工序 10)

## 负责人 30 秒拍板摘要卡 (Executive Gate)
- 预估 eCAC $0.60，熔断线 $0.70（不突破工序 02 LTV/3），超线由脚本自动熔断。
- 首次买量与新市场开拓需您审批预算。
- 定价继承工序 02 基线，本方案不改价。

{_fields({"ecac_usd": 0.6, "ecac_limit_usd": 0.7})}
## 一、ASO 词表
| 语言 | 核心词 | 长尾词 |
| --- | --- | --- |
| en | template maker | no ads template maker |

## 二、投放排期
| 周次 | 渠道 | 预算 (USD) |
| --- | --- | --- |
| W1 | TikTok | 300 |
| W2 | Reels | 200 |
"""


def _retention(name: str) -> str:
    return f"""# 《{name}》运营分析与 V1.1 Backlog (工序 11)

## 负责人 30 秒拍板摘要卡 (Executive Gate)
- 留存漏斗 D1 38% / D7 18% / D30 9%（演示占位，接入真实埋点后替换）。
- 最大流失点在 D1→D7，Backlog 优先解决回访动机。
- V1.1 Backlog 提交工序 05 PM 评审，不直接指挥研发。

{_fields({"d1_retention": 38, "d7_retention": 18, "d30_retention": 9, "is_major_version": False})}
## 一、留存衰减漏斗
| 节点 | 留存 |
| --- | --- |
| D1 | 38% |
| D7 | 18% |
| D30 | 9% |

## 二、V1.1 Backlog 建议书
| 优先级 | 需求 | 数据依据 |
| --- | --- | --- |
| P1 | 每日新模板提醒 | D1→D7 流失最大 |
| P2 | 历史作品二次编辑 | 回访用户中 30% 打开历史页 |
"""


def _unit_economics(name: str) -> str:
    return f"""# 《{name}》商业模式与单位经济 (工序 02)

## 负责人 30 秒拍板摘要卡 (Executive Gate)
- LTV/CAC 约 3.3，高于 3.0 放行线；回本周期在预算内。
- 商业护栏：不做开屏广告，保护商店评分。
- 需拍板：确认变现阶梯，定价以本工序为唯一来源。

{_fields({"organic_share": 0.35, "paid_cpi_usd": 1.0, "ad_arpu_usd": 0.9, "iap_conversion_rate": 0.05, "iap_net_arppu_usd": 25})}
## 一、混合变现阶梯
| 层级 | 权益 |
| --- | --- |
| 免费层 | 基础模板 + 激励视频解锁 |
| 24h 通行证 | 全量模板一天 |
| 年订阅 | 全量模板 + 无广告 |
| 终身买断 | 年订阅全部权益 |

## 二、单位经济测算表
| 指标 | 值 |
| --- | --- |
| 混合 CAC | $0.65 |
| 180 天 LTV | $2.15 |
| LTV/CAC | 3.3 |
"""


def build_simulated_deliverable(module_code: str, meta: Optional[Dict[str, Any]] = None) -> Tuple[str, Dict[str, str]]:
    """Returns (markdown content, extra workspace files) for a stage; None content means no template."""
    meta = meta or {}
    name = meta.get("product_name") or "当前产品"
    platform = str(meta.get("platform") or "ios").lower()
    extra: Dict[str, str] = {}
    builders = {
        "01": lambda: _market_research(name),
        "02": lambda: _unit_economics(name),
        "03": lambda: _direction(name),
        "04": lambda: _fakedoor(name),
        "05": lambda: _prd(name),
        "06": lambda: _design(name, platform),
        "07": lambda: _engineering(name),
        "08": lambda: _quality(name),
        "09": lambda: _release(name),
        "10": lambda: _acquisition(name),
        "11": lambda: _retention(name),
    }
    builder = builders.get(module_code)
    if builder is None:
        return "", extra
    if module_code == "04":
        extra["index.html"] = _fakedoor_html(name)
    if module_code == "06":
        from backend.app.services.design_bundle_sim import build_design_bundle

        extra.update(build_design_bundle(name, platform))
    from backend.app.services.delivery_contract import CONTRACT_STAGES, build_stage_manifest

    if module_code in CONTRACT_STAGES:
        extra["delivery.manifest.json"] = build_stage_manifest(module_code, f"交付物_{module_code}.md", platform)
    return SIMULATION_BANNER + builder(), extra
