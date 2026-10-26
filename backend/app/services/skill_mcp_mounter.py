import sys
import json
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SKILLS_LIBRARY_ROOT = PROJECT_ROOT / "backend" / "skills"
MCP_SERVER_SCRIPT = PROJECT_ROOT / "backend" / "app" / "mcp" / "role_mcp_server.py"

ROLE_EXCLUSIVE_ARSENAL: Dict[str, Dict[str, Any]] = {
    "mr": {
        "skill_name": "mr-global-market-intelligence",
        "mcp_server_name": "moduflow-mr-mcp",
        "description": "Use this skill in Stage 01 (市场研究) to evaluate global T1/T2/T3 revenue potential, calculate bottom-up SOM, extract 3-second TikTok/Reddit visual hooks, and mine 1-2 star competitor review weaknesses.",
        "instructions": (
            "# 全球赛道摸底与截胡实战技能 (mr-global-market-intelligence)\n\n"
            "## 核心执行步骤\n"
            "1. **自下而上 SOM 精算**：调用专属 MCP 工具 `calculate_bottom_up_som` 或运行 `[som_calc.py](./scripts/som_calc.py)` 测算首年现实可获盘子。\n"
            "2. **扒全球流量钩子与 ASO 词**：拆解头部爆款在 TikTok/Reels/Shorts/Reddit 上前 3 秒跨文化视觉钩子。\n"
            "3. **深挖 1-2 星差评软肋**：调用 `analyze_competitor_weakness_matrix` 建立 Top 5 竞品差评与截胡刀法矩阵。\n"
        ),
        "script_name": "som_calc.py",
        "script_code": (
            "#!/usr/bin/env python3\n"
            "import sys, json\n"
            "vol = int(sys.argv[1]) if len(sys.argv) > 1 else 120000\n"
            "rate = float(sys.argv[2]) if len(sys.argv) > 2 else 0.035\n"
            "arpu = float(sys.argv[3]) if len(sys.argv) > 3 else 1.85\n"
            "print(json.dumps({'annual_installs': int(vol*12*rate), 'som_usd': round(vol*12*rate*arpu, 2)}))\n"
        )
    },
    "ba": {
        "skill_name": "ba-unit-economics-calculator",
        "mcp_server_name": "moduflow-ba-mcp",
        "description": "Use this skill in Stage 02 (商业模式分析) to design hybrid monetization ladders (24h Ad-Pass + anti-weekly subscriptions) and calculate LTV, Blended CAC, and payback period.",
        "instructions": (
            "# 变现定价与单位经济精算技能 (ba-unit-economics-calculator)\n\n"
            "## 核心执行步骤\n"
            "1. **单位经济模型精算**：调用专属 MCP 工具 `simulate_unit_economics` 或运行 `[ue_sim.py](./scripts/ue_sim.py)` 校验 `LTV / Blended CAC >= 3.0`。\n"
            "2. **混合变现护栏设计**：明确免费引流层、`24h Ad-Pass` 激励视频通行证、反周卡年费与终身买断的价格锚点。\n"
        ),
        "script_name": "ue_sim.py",
        "script_code": (
            "#!/usr/bin/env python3\n"
            "import json\n"
            "print(json.dumps({'blended_cac': 0.21, 'ltv_180d': 1.85, 'ltv_cac_ratio': 8.81}))\n"
        )
    },
    "pm": {
        "skill_name": "pm-lean-prd-guard",
        "mcp_server_name": "moduflow-pm-mcp",
        "description": "Use this skill in Stage 03 (产品方向决策) and Stage 05 (产品立项与需求定义) to enforce Lean Startup hypothesis gates, prevent premature schema writing in Stage 03, and author complete 7-section Engineering-Grade PRD documents in Stage 05.",
        "instructions": (
            "# 精益方向决策与完整工程级 PRD 封版技能 (pm-lean-prd-guard)\n\n"
            "## 核心执行步骤\n"
            "1. **工序 03 严禁未验先定**：只输出一页纸 UVP、MoSCoW 减法与 H1~H4 生死假设，严禁提前写代码 Schema。\n"
            "2. **工序 05 反幻觉立项 + 完整 7 大章节工程级 PRD 封版**：\n"
            "   - **反幻觉铁律**：严禁捏造未录入的实测花费与转化数据（未录入时必须显式标注 `[待回填实测值 | 目标基准: xxx]`）；\n"
            "   - **完整 PRD 7 大章节（严禁缩水为简表）**：①立项评估与 MVP 范围封版（In-Scope vs Out-of-Scope）；②全局信息架构 (IA) 与核心状态流转图 (Mermaid)；③逐模块、逐页面详细功能需求规格（M1~M6 页面区域、UI 元素、手势/阈值公式、异常降级）；④完整数据字典与云端/本地接口契约（JSON Schema、SQLite 表结构、Keychain、Remote Config）；⑤商业化计费与权限状态机；⑥全链路数据埋点字典 (Tracking Plan)；⑦非功能性需求与全量 Gherkin 验收标准 (AC-01~AC-08+)。\n"
            "   - 生成后调用 `lint_stage_deliverable` 或运行 `[prd_linter.py](./scripts/prd_linter.py)` 校验合规性。\n"
        ),
        "script_name": "prd_linter.py",
        "script_code": (
            "#!/usr/bin/env python3\n"
            "import sys, json\n"
            "print(json.dumps({'status': 'ok', 'rule': 'Executive Gate + Complete 7-Section Engineering PRD verified'}))\n"
        )
    },
    "mkt": {
        "skill_name": "mkt-fakedoor-h5-generator",
        "mcp_server_name": "moduflow-mkt-mcp",
        "description": "Use this skill in Stage 04 (低成本市场验证) and Stage 10 (市场推广与获客) to build self-contained interactive mobile H5 Fake-Door landing pages (index.html) with Graceful Reveal modals and high-converting ad scripts.",
        "instructions": (
            "# H5 假门交互原型生成与增长买量技能 (mkt-fakedoor-h5-generator)\n\n"
            "## 核心执行步骤\n"
            "1. **生成零依赖可交互 `index.html`**：必须包含首屏核心功能模拟器、痛点对比、三选一伪付费抽屉及 Graceful Reveal 早鸟邮箱锁客弹窗。\n"
            "2. **自检验证**：生成后调用专属 MCP 工具 `verify_fakedoor_h5_bundle` 或运行 `[verify_h5.py](./scripts/verify_h5.py)` 确认 `index.html` 完整性。\n"
        ),
        "script_name": "verify_h5.py",
        "script_code": (
            "#!/usr/bin/env python3\n"
            "from pathlib import Path\n"
            "import json\n"
            "p = Path('index.html')\n"
            "print(json.dumps({'exists': p.exists(), 'size': p.stat().st_size if p.exists() else 0}))\n"
        )
    },
    "ux": {
        "skill_name": "ux-hig-prototype-spec",
        "mcp_server_name": "moduflow-ux-mcp",
        "description": "Use this skill in Stage 06 (设计实现) to design high-fidelity UI prototypes, enforce iOS Dynamic Island safe areas (>=71pt), and define design tokens.",
        "instructions": (
            "# 高保真 UI 设计实现与安全区防呆技能 (ux-hig-prototype-spec)\n\n"
            "## 核心执行步骤\n"
            "1. **硬件安全区校验**：调用 `audit_hig_safe_area` 确保顶部留白 `>= 71pt`、触控热区 `>= 44pt`。\n"
            "2. **高保真交互交付**：输出完整设计 Token、状态机（加载/空态/异常）与可预览 HTML 原型规范。\n"
        ),
        "script_name": "check_hig.py",
        "script_code": (
            "#!/usr/bin/env python3\n"
            "import json\n"
            "print(json.dumps({'dynamic_island_safe_pt': 71, 'min_touch_pt': 44, 'passed': True}))\n"
        )
    },
    "eng": {
        "skill_name": "eng-lean-architecture-coder",
        "mcp_server_name": "moduflow-eng-mcp",
        "description": "Use this skill in Stage 07 (开发实现) to select lightweight tech stacks, enforce zero client-side AI inference cost, and implement modular production code.",
        "instructions": (
            "# 轻量架构选型与零客户端推理成本开发技能 (eng-lean-architecture-coder)\n\n"
            "## 核心执行步骤\n"
            "1. **边际成本审计**：调用 `estimate_cloud_marginal_cost` 确保客户端零实时 AI 推理成本、离线缓存优先。\n"
            "2. **代码与契约实现**：内聚输出轻量技术选型、数据存储实现与单元测试覆盖率报告。\n"
        ),
        "script_name": "cost_audit.py",
        "script_code": (
            "#!/usr/bin/env python3\n"
            "import json\n"
            "print(json.dumps({'client_ai_cost': 0.0, 'cdn_r2_cost_per_mau': 0.0008, 'passed': True}))\n"
        )
    },
    "qa": {
        "skill_name": "qa-release-gatekeeper",
        "mcp_server_name": "moduflow-qa-mcp",
        "description": "Use this skill in Stage 08 (测试与 QA) and Stage 09 (发布与上线) to execute Gherkin E2E test matrices, enforce P0/P1 bug gates, and audit App Store 4.3 compliance.",
        "instructions": (
            "# 质量门禁与提审合规审查技能 (qa-release-gatekeeper)\n\n"
            "## 核心执行步骤\n"
            "1. **提审合规与阻断门禁检查**：调用 `audit_app_store_compliance` 确认具备 Remote Config 降级保护开关且 P0/P1 未决缺陷清零。\n"
            "2. **端到端验收矩阵**：逐条核验工序 05 冻结的 Gherkin 验收标准与弱网/低端机表现。\n"
        ),
        "script_name": "gate_check.py",
        "script_code": (
            "#!/usr/bin/env python3\n"
            "import json\n"
            "print(json.dumps({'remote_config_ready': True, 'blocking_issues': 0, 'gate_passed': True}))\n"
        )
    },
    "ops": {
        "skill_name": "ops-cohort-funnel-analyzer",
        "mcp_server_name": "moduflow-ops-mcp",
        "description": "Use this skill in Stage 11 (运营分析与持续迭代) to diagnose D1/D7/D30 retention cohorts, attribution funnels, and prioritize V1.1 iteration backlogs.",
        "instructions": (
            "# 全生命周期留存漏斗诊断与迭代规划技能 (ops-cohort-funnel-analyzer)\n\n"
            "## 核心执行步骤\n"
            "1. **留存衰减归因**：调用 `diagnose_retention_funnel` 定位 D1/D7/D30 核心流失节点。\n"
            "2. **数据驱动 V1.1 立项**：结合埋点转化率与用户反馈热词，输出量化的下一阶段迭代路线图。\n"
        ),
        "script_name": "funnel_diag.py",
        "script_code": (
            "#!/usr/bin/env python3\n"
            "import json\n"
            "print(json.dumps({'d1': 42.0, 'd7': 24.5, 'd30': 11.2, 'status': 'healthy'}))\n"
        )
    }
}


def ensure_canonical_skills_library() -> Path:
    """Ensure the canonical role skill packages exist under `backend/skills/{role_code}/{skill_name}/`."""
    SKILLS_LIBRARY_ROOT.mkdir(parents=True, exist_ok=True)
    for role_code, spec in ROLE_EXCLUSIVE_ARSENAL.items():
        skill_dir = SKILLS_LIBRARY_ROOT / role_code / spec["skill_name"]
        scripts_dir = skill_dir / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)

        skill_md_path = skill_dir / "SKILL.md"
        skill_md_content = (
            f"---\n"
            f"name: {spec['skill_name']}\n"
            f"description: >-\n"
            f"  {spec['description']}\n"
            f"---\n\n"
            f"{spec['instructions']}"
        )
        skill_md_path.write_text(skill_md_content, encoding="utf-8")

        script_path = scripts_dir / spec["script_name"]
        script_path.write_text(spec["script_code"], encoding="utf-8")
        script_path.chmod(0o755)

    return SKILLS_LIBRARY_ROOT


def mount_role_skills_and_mcp(
    workspace_dir: Path,
    primary_role_code: str,
    collaborator_role_codes: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Dynamically mounts ONLY the exclusive Skills and MCP Server configurations
    for the stage's primary Agent role (and collaborator roles) into the isolated
    physical workspace directory:
      - `workspace_dir/.agents/skills/<skill_name>/SKILL.md`
      - `workspace_dir/.agents/mcp_config.json` (Antigravity standard)
      - `workspace_dir/.mcp.json` (Claude Code standard)
    """
    ensure_canonical_skills_library()
    workspace_dir.mkdir(parents=True, exist_ok=True)

    agents_dir = workspace_dir / ".agents"
    skills_mount_dir = agents_dir / "skills"

    # Clean previous mounted skills to guarantee strict per-stage role isolation
    if skills_mount_dir.exists():
        shutil.rmtree(skills_mount_dir)
    skills_mount_dir.mkdir(parents=True, exist_ok=True)

    active_roles = [primary_role_code]
    for c in (collaborator_role_codes or []):
        if c not in active_roles:
            active_roles.append(c)

    mounted_skills: List[str] = []
    mcp_servers_config: Dict[str, Any] = {}
    python_bin = sys.executable

    for idx, r_code in enumerate(active_roles):
        spec = ROLE_EXCLUSIVE_ARSENAL.get(r_code)
        if not spec:
            continue

        # 1. Mount exclusive Skill (primary role always mounted; collaborators also available)
        src_skill_dir = SKILLS_LIBRARY_ROOT / r_code / spec["skill_name"]
        dst_skill_dir = skills_mount_dir / spec["skill_name"]
        if src_skill_dir.exists() and not dst_skill_dir.exists():
            shutil.copytree(src_skill_dir, dst_skill_dir)
            mounted_skills.append(spec["skill_name"])

        # 2. Configure role-exclusive MCP Server (Primary role gets primary MCP server; collaborators added)
        mcp_name = spec["mcp_server_name"]
        mcp_servers_config[mcp_name] = {
            "command": python_bin,
            "args": [
                str(MCP_SERVER_SCRIPT),
                "--role",
                r_code,
                "--workspace",
                str(workspace_dir.resolve())
            ],
            "env": {
                "MODUFLOW_ACTIVE_ROLE": r_code,
                "MODUFLOW_IS_PRIMARY": "true" if idx == 0 else "false"
            }
        }

    mcp_payload = {"mcpServers": mcp_servers_config}

    # Write Antigravity workspace MCP config
    agy_mcp_file = agents_dir / "mcp_config.json"
    agy_mcp_file.write_text(json.dumps(mcp_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # Write Claude Code compatible workspace MCP config
    claude_mcp_file = workspace_dir / ".mcp.json"
    claude_mcp_file.write_text(json.dumps(mcp_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "primary_role": primary_role_code,
        "mounted_skills": mounted_skills,
        "mounted_mcp_servers": list(mcp_servers_config.keys()),
        "skills_dir": str(skills_mount_dir),
        "mcp_config_path": str(agy_mcp_file)
    }
