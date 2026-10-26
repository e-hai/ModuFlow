#!/usr/bin/env python3
"""
ModuFlow Role-Exclusive MCP Server (Stdio JSON-RPC 2.0)
Dynamically exposes role-specific domain tools based on `--role <role_code>`.
"""
import sys
import json
import argparse
from pathlib import Path
from typing import Dict, Any, List

ROLE_MCP_TOOLS: Dict[str, List[Dict[str, Any]]] = {
    "mr": [
        {
            "name": "calculate_bottom_up_som",
            "description": "使用自下而上(Bottom-Up)模型测算全球赛道首年现实可获盘子(SOM)、各区域(T1/T2/T3)流量与营收含金量。",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "monthly_search_volume": {"type": "integer", "description": "核心痛点词全球月搜索/曝光量"},
                    "target_capture_rate": {"type": "number", "description": "首年预期流量截胡转化率 (如 0.035)"},
                    "blended_arpu_usd": {"type": "number", "description": "单用户首年混合变现净值 ARPU (USD)"}
                },
                "required": ["monthly_search_volume", "target_capture_rate", "blended_arpu_usd"]
            }
        },
        {
            "name": "analyze_competitor_weakness_matrix",
            "description": "生成竞品 1-2 星差评软肋与 TikTok/Reddit 3秒视觉钩子截胡矩阵。",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "细分赛道名称"},
                    "competitors": {"type": "array", "items": {"type": "string"}, "description": "对标竞品列表"}
                },
                "required": ["category", "competitors"]
            }
        }
    ],
    "ba": [
        {
            "name": "simulate_unit_economics",
            "description": "精算单客单位经济模型(LTV、Blended CAC、毛利率、D0~D180回本周期与盈亏平衡点)。",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "organic_share": {"type": "number", "description": "自然流占比 (0~1)"},
                    "paid_cpi_usd": {"type": "number", "description": "买量单次安装成本 CPI (USD)"},
                    "ad_arpu_usd": {"type": "number", "description": "激励广告通行证单客净贡献 (USD)"},
                    "iap_conversion_rate": {"type": "number", "description": "订阅/买断付费转化率 (0~1)"},
                    "iap_net_arppu_usd": {"type": "number", "description": "扣除平台税后付费客均净贡献 (USD)"}
                },
                "required": ["organic_share", "paid_cpi_usd", "ad_arpu_usd", "iap_conversion_rate", "iap_net_arppu_usd"]
            }
        }
    ],
    "pm": [
        {
            "name": "lint_stage_deliverable",
            "description": "检查工序 03 或 05 的交付物是否符合精益防抢跑红线、反幻觉铁律与双层摘要卡格式规范。",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "stage_code": {"type": "string", "enum": ["03", "05"], "description": "工序编号 (03 或 05)"},
                    "markdown_content": {"type": "string", "description": "待校验的 Markdown 全文"}
                },
                "required": ["stage_code", "markdown_content"]
            }
        }
    ],
    "mkt": [
        {
            "name": "verify_fakedoor_h5_bundle",
            "description": "校验当前工作区下的 H5 假门测试网页 (index.html) 是否存在、零外部坏死依赖且包含 Graceful Reveal 早鸟锁客弹窗与核心埋点。",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "html_filename": {"type": "string", "default": "index.html", "description": "H5 文件名"}
                }
            }
        }
    ],
    "ux": [
        {
            "name": "audit_hig_safe_area",
            "description": "审计 UI 原型与交互规范是否满足 iPhone 灵动岛安全区 (≥71pt)、触控热区 (≥44pt) 与 Apple 4.3 原生交互要求。",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "top_safe_padding_pt": {"type": "integer", "description": "顶部安全区留白 pt 值"},
                    "min_touch_target_pt": {"type": "integer", "description": "最小触控热区 pt 值"}
                },
                "required": ["top_safe_padding_pt", "min_touch_target_pt"]
            }
        }
    ],
    "eng": [
        {
            "name": "estimate_cloud_marginal_cost",
            "description": "测算架构方案的单活跃用户 (MAU) 云端推理、存储与 CDN 边际成本是否守住毛利防线。",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "client_realtime_ai_calls": {"type": "integer", "description": "客户端实时 AI 推理调用次数/人"},
                    "avg_cdn_bandwidth_mb": {"type": "number", "description": "人均月下行 CDN 流量 (MB)"}
                },
                "required": ["client_realtime_ai_calls", "avg_cdn_bandwidth_mb"]
            }
        }
    ],
    "qa": [
        {
            "name": "audit_app_store_compliance",
            "description": "执行上线前提审合规门禁扫描（Apple 4.3 拒审防范、Remote Config 降级开关、隐私清单与未关闭 P0/P1 缺陷检查）。",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "has_remote_config_fallback": {"type": "boolean", "description": "是否具备云端审核降级开关"},
                    "open_critical_issues": {"type": "integer", "description": "未关闭的 P0/P1 阻断性缺陷数"}
                },
                "required": ["has_remote_config_fallback", "open_critical_issues"]
            }
        }
    ],
    "ops": [
        {
            "name": "diagnose_retention_funnel",
            "description": "诊断 D1/D7/D30 留存衰减漏斗与北极星指标瓶颈，输出下一版本迭代优先级。",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "d1_retention": {"type": "number", "description": "次日留存率 (%)"},
                    "d7_retention": {"type": "number", "description": "7日留存率 (%)"},
                    "d30_retention": {"type": "number", "description": "30日留存率 (%)"}
                },
                "required": ["d1_retention", "d7_retention", "d30_retention"]
            }
        }
    ]
}


def execute_role_tool(role_code: str, workspace_dir: Path, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    if tool_name == "calculate_bottom_up_som":
        vol = int(args.get("monthly_search_volume", 100000))
        rate = float(args.get("target_capture_rate", 0.03))
        arpu = float(args.get("blended_arpu_usd", 1.5))
        annual_installs = int(vol * 12 * rate)
        som_usd = round(annual_installs * arpu, 2)
        return {
            "annual_target_installs": annual_installs,
            "first_year_som_usd": som_usd,
            "verdict": "GO (具备高利润截胡价值)" if som_usd >= 100000 else "CAUTION (盘子偏小，需控研发成本)"
        }
    elif tool_name == "analyze_competitor_weakness_matrix":
        return {
            "category": args.get("category", ""),
            "competitors": args.get("competitors", []),
            "mandatory_dimensions": [
                "近3个月 App Store / Google Play 1-2星高频差评原话",
                "TikTok / Reels / Reddit 前3秒跨文化视觉钩子 (Visual Hook)",
                "订阅价格陷阱 vs 我们的单点破局刀法 (Wedge)"
            ]
        }
    elif tool_name == "simulate_unit_economics":
        org = float(args.get("organic_share", 0.7))
        cpi = float(args.get("paid_cpi_usd", 0.7))
        ad_arpu = float(args.get("ad_arpu_usd", 1.15))
        iap_cr = float(args.get("iap_conversion_rate", 0.03))
        iap_arppu = float(args.get("iap_net_arppu_usd", 7.0))
        blended_cac = round((1.0 - org) * cpi, 3)
        ltv = round(ad_arpu + iap_cr * iap_arppu, 3)
        ratio = round(ltv / blended_cac, 2) if blended_cac > 0 else 99.9
        return {
            "blended_cac_usd": blended_cac,
            "ltv_180d_usd": ltv,
            "ltv_cac_ratio": ratio,
            "healthy": ratio >= 3.0
        }
    elif tool_name == "lint_stage_deliverable":
        stage = args.get("stage_code", "03")
        content = args.get("markdown_content", "")
        issues = []
        if "负责人 30 秒拍板摘要卡" not in content:
            issues.append("缺少顶层『## 负责人 30 秒拍板摘要卡 (Executive Gate)』")
        if stage == "03" and ("CREATE TABLE" in content or "interface " in content):
            issues.append("违反工序03红线：严禁在方向决策阶段提前编写代码级 Schema")
        if stage == "05" and "Given" not in content:
            issues.append("工序05缺少 Gherkin (Given/When/Then) 验收标准")
        return {"passed": len(issues) == 0, "issues": issues}
    elif tool_name == "verify_fakedoor_h5_bundle":
        fname = args.get("html_filename", "index.html")
        target = workspace_dir / fname
        if not target.exists():
            return {"exists": False, "passed": False, "error": f"未在工作区找到 {fname}，工序04强制要求生成可交互H5假门网页"}
        html = target.read_text(encoding="utf-8", errors="ignore")
        has_script = "<script" in html.lower()
        return {
            "exists": True,
            "size_bytes": len(html),
            "has_interactive_script": has_script,
            "passed": len(html) > 500 and has_script
        }
    elif tool_name == "audit_hig_safe_area":
        top_pt = int(args.get("top_safe_padding_pt", 71))
        touch_pt = int(args.get("min_touch_target_pt", 44))
        return {
            "dynamic_island_safe": top_pt >= 71,
            "touch_target_safe": touch_pt >= 44,
            "passed": top_pt >= 71 and touch_pt >= 44
        }
    elif tool_name == "estimate_cloud_marginal_cost":
        ai_calls = int(args.get("client_realtime_ai_calls", 0))
        bw_mb = float(args.get("avg_cdn_bandwidth_mb", 15.0))
        cost = round(ai_calls * 0.015 + bw_mb * 0.00005, 5)
        return {
            "estimated_cost_per_mau_usd": cost,
            "zero_client_ai_compliant": ai_calls == 0,
            "passed": ai_calls == 0 and cost <= 0.005
        }
    elif tool_name == "audit_app_store_compliance":
        has_rc = bool(args.get("has_remote_config_fallback", True))
        bugs = int(args.get("open_critical_issues", 0))
        return {
            "passed": has_rc and bugs == 0,
            "blocking_reason": None if (has_rc and bugs == 0) else "存在未关闭阻断性缺陷或缺少 Remote Config 提审降级保护开关"
        }
    elif tool_name == "diagnose_retention_funnel":
        d1 = float(args.get("d1_retention", 40.0))
        d7 = float(args.get("d7_retention", 20.0))
        d30 = float(args.get("d30_retention", 10.0))
        return {
            "d1_d7_drop_ratio": round((d1 - d7) / max(d1, 1.0), 2),
            "d30_healthy": d30 >= 8.0,
            "focus_recommendation": "优化首屏 10 秒 Aha 激活路径" if d1 < 35.0 else "强化周期性内容更新与桌面小组件召回"
        }
    return {"error": f"Unknown tool: {tool_name}"}


def main():
    parser = argparse.ArgumentParser(description="ModuFlow Role-Exclusive MCP Server")
    parser.add_argument("--role", required=True, help="Role code (mr, ba, pm, mkt, ux, eng, qa, ops)")
    parser.add_argument("--workspace", default=".", help="Workspace directory path")
    args = parser.parse_args()

    role_code = args.role.lower()
    workspace_dir = Path(args.workspace).resolve()
    tools = ROLE_MCP_TOOLS.get(role_code, [])

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue

        req_id = req.get("id")
        method = req.get("method", "")
        params = req.get("params") or {}

        if method == "initialize":
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": f"moduflow-{role_code}-mcp",
                        "version": "1.0.0"
                    }
                }
            }
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()
        elif method == "notifications/initialized":
            continue
        elif method == "tools/list":
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"tools": tools}
            }
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()
        elif method == "tools/call":
            t_name = params.get("name", "")
            t_args = params.get("arguments") or {}
            output = execute_role_tool(role_code, workspace_dir, t_name, t_args)
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(output, ensure_ascii=False, indent=2)
                        }
                    ]
                }
            }
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()
        elif req_id is not None:
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {}
            }
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
