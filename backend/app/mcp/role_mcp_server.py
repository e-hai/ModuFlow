#!/usr/bin/env python3
"""
ModuFlow Role-Exclusive MCP Server (Stdio JSON-RPC 2.0)
Dynamically exposes role-specific domain tools based on `--role <role_code>`.
"""
import sys
import os
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
        },
        {
            "name": "audit_material_spec",
            "description": "审计 UI 原型与交互规范是否满足 Android Material 3 规范（触控热区 ≥48dp、状态栏/挖孔避让留白 ≥24~48dp 与 Google Play 交互要求）。",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "status_bar_safe_dp": {"type": "integer", "description": "顶部状态栏/挖孔避让留白 dp 值"},
                    "min_touch_target_dp": {"type": "integer", "description": "最小触控热区 dp 值"}
                },
                "required": ["status_bar_safe_dp", "min_touch_target_dp"]
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
                    "avg_cdn_bandwidth_mb": {"type": "number", "description": "人均月下行 CDN 流量 (MB)"},
                    "enforce_zero_inference": {"type": "boolean", "description": "是否严格执行客户端零推理成本"}
                },
                "required": ["client_realtime_ai_calls", "avg_cdn_bandwidth_mb"]
            }
        },
        {
            "name": "audit_client_zero_inference",
            "description": "根据项目 profile 参数化审计客户端实时 AI 推理调用与云端毛利防线。",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "client_realtime_ai_calls": {"type": "integer", "description": "客户端实时 AI 推理调用次数/人"},
                    "avg_cdn_bandwidth_mb": {"type": "number", "description": "人均月下行 CDN 流量 (MB)"},
                    "enforce_zero_inference": {"type": "boolean", "description": "是否严格执行客户端零推理成本"}
                },
                "required": ["client_realtime_ai_calls"]
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


PLATFORM_ONLY_TOOLS = {
    "audit_hig_safe_area": "ios",
    "audit_material_spec": "android",
}
COLLABORATOR_NOTE = "（协作角色调用：结果仅供参考，不作为本工序关口证据）"


def visible_tools(role_code: str, platform: str = "ios", is_primary: bool = True) -> List[Dict[str, Any]]:
    """Tools of this role, filtered to the project platform; collaborator copies are labelled advisory."""
    from backend.app.services.profile_guard import covers_android, covers_ios

    targets = set()
    if covers_ios(platform):
        targets.add("ios")
    if covers_android(platform):
        targets.add("android")
    tools = []
    for tool in ROLE_MCP_TOOLS.get(role_code, []):
        only = PLATFORM_ONLY_TOOLS.get(tool["name"])
        if only and only not in targets:
            continue
        entry = dict(tool)
        if not is_primary:
            entry["description"] = entry["description"] + COLLABORATOR_NOTE
        tools.append(entry)
    return tools


def call_tool(
    role_code: str,
    workspace_dir: Path,
    tool_name: str,
    args: Dict[str, Any],
    platform: str = "ios",
    is_primary: bool = True,
) -> Dict[str, Any]:
    allowed = {tool["name"] for tool in visible_tools(role_code, platform, is_primary)}
    if tool_name not in allowed:
        return {
            "passed": False,
            "error": f"工具 {tool_name} 不属于角色 {role_code}（平台 {platform}）的工具箱，已拒绝执行",
        }
    output = execute_role_tool(role_code, workspace_dir, tool_name, args)
    output["caller_role"] = role_code
    output["caller_is_primary"] = is_primary
    if not is_primary:
        output["advisory_only"] = True
    return output


def _deliverable_audit():
    root = Path(__file__).resolve().parents[3]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from backend.app.services import deliverable_audit
    return deliverable_audit


def execute_role_tool(role_code: str, workspace_dir: Path, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Run a role tool against workspace files. Caller arguments are claims only."""
    audit = _deliverable_audit()
    claimed = dict(args or {})
    if tool_name == "calculate_bottom_up_som":
        return audit.audit_som_workspace(workspace_dir, claimed=claimed)
    elif tool_name == "analyze_competitor_weakness_matrix":
        texts = audit.collect_workspace_texts(workspace_dir)
        evidence = bool(texts)
        return {
            "category": claimed.get("category", ""),
            "competitors": claimed.get("competitors", []),
            "passed": evidence,
            "evidence_found": evidence,
            "reasons": [] if evidence else ["工作区没有竞品材料，调用方名单不能单独放行"],
            "mandatory_dimensions": [
                "近3个月 App Store / Google Play 1-2星高频差评原话",
                "TikTok / Reels / Reddit 前3秒跨文化视觉钩子 (Visual Hook)",
                "订阅价格陷阱 vs 我们的单点破局刀法 (Wedge)"
            ],
        }
    elif tool_name == "simulate_unit_economics":
        return audit.audit_unit_economics_workspace(workspace_dir, claimed=claimed)
    elif tool_name == "lint_stage_deliverable":
        content = claimed.get("markdown_content") or ""
        if not str(content).strip():
            return {"passed": False, "score": 0, "reasons": ["没有 PRD 正文"]}
        result = audit.lint_markdown(str(content))
        result["reasons"] = list(result.get("warnings") or [])
        if not result.get("passed"):
            result["reasons"].insert(0, f"PRD 得分 {result.get('score')}，放行线为 100")
        return result
    elif tool_name == "verify_fakedoor_h5_bundle":
        return audit.audit_fakedoor_workspace(workspace_dir, claimed=claimed)
    elif tool_name == "audit_hig_safe_area":
        return audit.audit_design_workspace(workspace_dir, platform="ios", claimed=claimed)
    elif tool_name == "audit_material_spec":
        return audit.audit_design_workspace(workspace_dir, platform="android", claimed=claimed)
    elif tool_name in ["estimate_cloud_marginal_cost", "audit_client_zero_inference"]:
        enforce_zero = os.getenv("MODUFLOW_ZERO_INFERENCE", "true").lower() != "false"
        result = audit.audit_inference_workspace(workspace_dir, claimed=claimed, enforce_zero=enforce_zero)
        calls = int(result.get("client_realtime_ai_calls") or 0)
        result["estimated_cost_per_mau_usd"] = round(calls * 0.015, 5)
        result["mode"] = "strict_zero_client_inference" if enforce_zero else "edge_ai_permitted"
        return result
    elif tool_name == "audit_app_store_compliance":
        return audit.audit_qa_workspace(workspace_dir, claimed=claimed, require_remote_config=True)
    elif tool_name == "diagnose_retention_funnel":
        return audit.audit_retention_workspace(workspace_dir, claimed=claimed)
    return {"error": f"Unknown tool: {tool_name}", "passed": False}


def main():
    parser = argparse.ArgumentParser(description="ModuFlow Role-Exclusive MCP Server")
    parser.add_argument("--role", required=True, help="Role code (mr, ba, pm, mkt, ux, eng, qa, ops)")
    parser.add_argument("--workspace", default=".", help="Workspace directory path")
    args = parser.parse_args()

    role_code = args.role.lower()
    workspace_dir = Path(args.workspace).resolve()
    platform = os.getenv("MODUFLOW_PLATFORM", "ios")
    is_primary = os.getenv("MODUFLOW_IS_PRIMARY", "true").lower() != "false"
    tools = visible_tools(role_code, platform, is_primary)

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
            output = call_tool(role_code, workspace_dir, t_name, t_args, platform, is_primary)
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
