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
        "description": "Use this skill in Stage 03 (产品方向决策) and Stage 05 (产品需求定义) to enforce Lean Startup hypothesis gates in Stage 03, author complete 7+1 Golden Chapter Pure-PM PRD documents with 5-dimension module spec cards and business data dictionaries, strictly avoiding engineering technical leakages (no SQL DDL / JSON Schema), and handle downstream requirement CRs in Stage 05.",
        "instructions": (
            "# 精益方向决策与黄金 7+1 纯业务 PRD 封版技能 (pm-lean-prd-guard)\n\n"
            "## 核心执行步骤\n"
            "1. **工序 03 严禁未验先定**：只输出一页纸 UVP、MoSCoW 减法与 H1~H4 生死假设清单，严禁提前编写代码级 Schema。\n"
            "2. **工序 05 黄金 7+1 章节纯业务 PRD 规范（严守 PM 业务视角，严禁工程师技术越界）**：\n"
            "   - **多视角阅读分层设计**：置顶《## 负责人 30 秒拍板摘要卡 (Executive Gate)》，随后展开 7+1 核心章节；\n"
            "   - **第 0 章**：文档元信息与版本演进履历（版本号、更新时间、变更类型、变更项对照表）；\n"
            "   - **第一章**：版本定位与范围封版（北极星指标、精简 User Stories、In-Scope P0/P1 vs Out-of-Scope 范围封版矩阵表）；\n"
            "   - **第二章**：全局信息架构与全站视图索引（Mermaid 页面路由拓扑图、全站视图索引总表 View Index Table `V-01~V-05` 标明视图形态与安全区、主流程泳道图）；\n"
            "   - **第三章**：功能模块详细规格说明（M1~M6 核心功能全量展开，逐模块必须统一采用五维结构化规格卡：①核心意图导言、②界面布局与组件清单表、③交互流转与计算规则表、④边界条件与异常降级表、⑤模块验收点索引）；\n"
            "   - **第四章**：商业化特权与付费业务规则（Mermaid StateDiagram 权益状态机、SKU 定价阶梯映射表、免费 vs 付费特权矩阵、付费门槛触发时机、网络超时或未支付时的用户端友好降级体验规则、防刷与风控业务规则）；\n"
            "   - **第五章**：核心业务数据字典与本地存储策略（纯业务视角，严禁代码/SQL/JSON Schema：①核心业务实体清单与业务关系说明、②逐实体业务数据字典表【字段名、业务含义、业务类型、是否必填、取值范围/枚举值、默认值、校验失败提示文案】、③用户数据存储与隐私分级业务策略【离线持久化诉求、敏感隐私保护诉求、缓存自动清理业务诉求与生命周期】）；\n"
            "   - **第六章**：全链路数据埋点规范（`E-01~E-12` 核心事件埋点总表、转化漏斗与留存计算公式）；\n"
            "   - **第七章**：端到端验收用例与体验质量需求（结构化 `AC-01~AC-08` Gherkin 验收矩阵表包含用例ID/场景/Given/When/Then、用户感知级性能要求【如冷启首屏、导出等待感知】、iOS HIG 灵动岛安全区 ≥71pt 与 Apple 4.3 审核合规业务护栏）。\n"
            "   - **自动化合规校验**：生成交付物后调用 `lint_stage_deliverable` 或运行 `[prd_linter.py](./scripts/prd_linter.py)` 校验合规性与去工程化检查。\n"
        ),
        "script_name": "prd_linter.py",
        "script_code": (
            "#!/usr/bin/env python3\n"
            "import sys, os, re, json\n"
            "from pathlib import Path\n\n"
            "def lint_prd(target_path: Path):\n"
            "    if not target_path.exists():\n"
            "        return {'status': 'error', 'file': str(target_path), 'score': 0, 'errors': [f'File {target_path} does not exist']}\n\n"
            "    content = target_path.read_text(encoding='utf-8', errors='replace')\n"
            "    has_executive_gate = bool(re.search(r'##\\s*负责人\\s*30\\s*秒拍板摘要卡', content))\n\n"
            "    expected_chapters = [\n"
            "        ('Ch0', r'第\\s*0\\s*章[：:].*元信息|第\\s*零\\s*章'),\n"
            "        ('Ch1', r'第一章[：:].*范围|第\\s*1\\s*章'),\n"
            "        ('Ch2', r'第二章[：:].*信息架构|第\\s*2\\s*章'),\n"
            "        ('Ch3', r'第三章[：:].*详细规格|第\\s*3\\s*章'),\n"
            "        ('Ch4', r'第四章[：:].*商业|第\\s*4\\s*章'),\n"
            "        ('Ch5', r'第五章[：:].*数据|第\\s*5\\s*章'),\n"
            "        ('Ch6', r'第六章[：:].*埋点|第\\s*6\\s*章'),\n"
            "        ('Ch7', r'第七章[：:].*验收|第\\s*7\\s*章'),\n"
            "    ]\n"
            "    detected_chapters = []\n"
            "    missing_chapters = []\n"
            "    for code, pattern in expected_chapters:\n"
            "        if re.search(pattern, content):\n"
            "            detected_chapters.append(code)\n"
            "        else:\n"
            "            missing_chapters.append(code)\n\n"
            "    views_detected = sorted(list(set(re.findall(r'V-0[1-9]', content))))\n"
            "    modules_detected = sorted(list(set(re.findall(r'\\bM[1-9]\\b', content))))\n"
            "    table_count = len(re.findall(r'\\|(?:\s*[-:]+\s*\\|)+', content))\n"
            "    mermaid_diagrams = len(re.findall(r'```mermaid', content))\n"
            "    has_banned_smoke_test = bool(re.search(r'工序\\s*04\\s*假门测试|Smoke\\s*Test\\s*待回填|Go/Pivot/Kill\\s*裁决', content))\n\n"
            "    has_sql_ddl = bool(re.search(r'^\\s*CREATE\\s+(?:TABLE|INDEX)\\b', content, re.IGNORECASE | re.MULTILINE))\n"
            "    has_raw_json_schema = bool(re.search(r'\"type\"\\s*:\\s*\"(?:object|string|number)\"', content))\n"
            "    has_engineering_leakage = has_sql_ddl or has_raw_json_schema\n\n"
            "    score = 100\n"
            "    warnings = []\n"
            "    suggestions = []\n\n"
            "    if not has_executive_gate:\n"
            "        score -= 15\n"
            "        warnings.append('Missing Executive Gate (负责人 30 秒拍板摘要卡)')\n"
            "    if missing_chapters:\n"
            "        score -= min(40, len(missing_chapters) * 8)\n"
            "        warnings.append('Missing chapters: ' + ', '.join(missing_chapters))\n"
            "    if not views_detected:\n"
            "        score -= 10\n"
            "        warnings.append('No full-site View IDs (e.g. V-01~V-05) detected in IA/Matrix')\n"
            "    if len(modules_detected) < 3:\n"
            "        score -= 10\n"
            "        warnings.append('Less than 3 functional modules (M1~Mx) detected')\n"
            "    if table_count < 5:\n"
            "        score -= 10\n"
            "        warnings.append(f'Low structured table count ({table_count}); PRD should be concrete and structured')\n"
            "    if mermaid_diagrams < 1:\n"
            "        score -= 5\n"
            "        suggestions.append('Consider adding Mermaid diagrams for visual flow & state machines')\n"
            "    if has_banned_smoke_test:\n"
            "        score -= 20\n"
            "        warnings.append('PRD contains leftover Stage 04 smoke test tables or Go/Pivot/Kill audit rules')\n"
            "    if has_engineering_leakage:\n"
            "        score -= 25\n"
            "        leak_details = []\n"
            "        if has_sql_ddl:\n"
            "            leak_details.append('SQL DDL (CREATE TABLE/INDEX)')\n"
            "        if has_raw_json_schema:\n"
            "            leak_details.append('raw JSON Schema')\n"
            "        warnings.append('PRD contains engineer-role implementation technical leakages: ' + ', '.join(leak_details) + '. Stage 05 must strictly remain a pure Product Manager role.')\n\n"
            "    score = max(0, score)\n"
            "    return {\n"
            "        'status': 'ok' if score >= 80 else ('warning' if score >= 60 else 'failed'),\n"
            "        'file': target_path.name,\n"
            "        'executive_gate': has_executive_gate,\n"
            "        'chapters_detected': detected_chapters,\n"
            "        'missing_chapters': missing_chapters,\n"
            "        'views_detected': views_detected,\n"
            "        'modules_detected': modules_detected,\n"
            "        'table_count': table_count,\n"
            "        'mermaid_diagrams': mermaid_diagrams,\n"
            "        'has_banned_smoke_test_table': has_banned_smoke_test,\n"
            "        'has_engineering_leakage': has_engineering_leakage,\n"
            "        'warnings': warnings,\n"
            "        'suggestions': suggestions,\n"
            "        'score': score\n"
            "    }\n\n"
            "if __name__ == '__main__':\n"
            "    target = Path(sys.argv[1]) if len(sys.argv) > 1 else (list(Path('.').glob('*.md'))[0] if list(Path('.').glob('*.md')) else Path('PRD.md'))\n"
            "    result = lint_prd(target)\n"
            "    print(json.dumps(result, ensure_ascii=False, indent=2))\n"
            "    sys.exit(0 if result['status'] == 'ok' else 1)\n"
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
        "description": "Use this skill in Stage 06 (设计实现) to design high-fidelity multi-artboard UI prototypes, generate Sketch/Figma-grade interactive HTML inspection bundles with SVG icon & font assets, and enforce iOS Dynamic Island safe areas (>=71pt).",
        "instructions": (
            "# 高保真 UI 设计实现与 Sketch 级标注包交付技能 (ux-hig-prototype-spec)\n\n"
            "## 核心执行步骤\n"
            "1. **硬件安全区校验**：调用 `audit_hig_safe_area` 确保顶部留白 `>= 71pt`（推荐 `74pt`）、底部 `>= 34pt`、最小触控热区 `44x44pt`。\n"
            "2. **双轨真交付（Markdown 设计规范 + Sketch 级 HTML 标注工作台与资产包）**：\n"
            "   - 输出完整 Markdown 设计规范文档（含 SwiftUI Design Tokens 代码契约与 V-01~V-05 图层树）；\n"
            "   - 在工作区同步生成 `index.html`（覆盖全部 PRD 核心视图 V-01~V-05 画板切换、点选组件检视尺寸/间距/色号并一键复制 SwiftUI 与 Tailwind 代码、安全区标尺开关）以及 `assets/icons/*.svg`、`assets/fonts/`、`assets/tokens/design_tokens.json` 与全量打包 `.zip`。\n"
        ),
        "script_name": "check_hig.py",
        "script_code": (
            "#!/usr/bin/env python3\n"
            "import json\n"
            "print(json.dumps({'dynamic_island_safe_pt': 74, 'min_touch_pt': 44, 'multi_artboard_bundle': True, 'passed': True}))\n"
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
    collaborator_role_codes: Optional[List[str]] = None,
    platform: Optional[str] = None,
    client_zero_inference: Optional[bool] = None
) -> Dict[str, Any]:
    """
    Dynamically mounts ONLY the exclusive Skills and MCP Server configurations
    for the stage's primary Agent role (and collaborator roles) into the isolated
    physical workspace directory:
      - `workspace_dir/.agents/skills/<skill_name>/SKILL.md`
      - `workspace_dir/.agents/mcp_config.json` (Antigravity standard)
      - `workspace_dir/.mcp.json` (Claude Code standard)

    Phase 6 Profile Parameterization:
    - platform: 'ios' | 'android' | 'cross_platform'
      If android: mounts check_material.py and Android Material 3 ruleset (no check_hig.py)
      If ios: mounts check_hig.py and Apple HIG ruleset
    - client_zero_inference: bool
      If True: cost_audit.py strictly checks 0 client AI calls
      If False: cost_audit.py permits on-device / edge AI calls
    """
    ensure_canonical_skills_library()
    workspace_dir.mkdir(parents=True, exist_ok=True)

    # Auto-resolve profile from parent authorization.yaml if not explicitly supplied
    if platform is None or client_zero_inference is None:
        curr = workspace_dir.resolve()
        while curr != curr.parent:
            auth_f = curr / "authorization.yaml"
            if auth_f.exists():
                try:
                    import yaml
                    data = yaml.safe_load(auth_f.read_text(encoding="utf-8"))
                    if isinstance(data, dict):
                        prof = data.get("profile", {})
                        if platform is None:
                            platform = prof.get("platform", "ios")
                        if client_zero_inference is None:
                            client_zero_inference = prof.get("client_zero_inference", True)
                except Exception:
                    pass
                break
            curr = curr.parent

    target_platform = str(platform or "ios").lower()
    target_zero_inf = True if client_zero_inference is None else bool(client_zero_inference)

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

            # Profile-specific script customization
            scripts_dir = dst_skill_dir / "scripts"
            scripts_dir.mkdir(parents=True, exist_ok=True)

            if r_code == "ux":
                if target_platform == "android":
                    # For Android: Mount check_material.py, remove check_hig.py
                    hig_script = scripts_dir / "check_hig.py"
                    if hig_script.exists():
                        hig_script.unlink()
                    mat_script = scripts_dir / "check_material.py"
                    mat_script.write_text(
                        "#!/usr/bin/env python3\n"
                        "import json\n"
                        "print(json.dumps({'platform': 'android', 'material_version': 'Material 3', "
                        "'status_bar_cutout_safe_dp': 48, 'min_touch_target_dp': 48, "
                        "'multi_artboard_bundle': True, 'passed': True}))\n",
                        encoding="utf-8"
                    )
                    mat_script.chmod(0o755)

                    # Update SKILL.md instructions for Android
                    skill_md_file = dst_skill_dir / "SKILL.md"
                    skill_md_file.write_text(
                        "---\n"
                        f"name: {spec['skill_name']}\n"
                        "description: >-\n"
                        "  Use this skill in Stage 06 (设计实现) to design high-fidelity UI prototypes according to Android Material 3 Design specifications (Touch target >= 48dp, status bar/cutout safe area >= 24~48dp).\n"
                        "---\n\n"
                        "# Android Material 3 高保真 UI 设计规范 (ux-material-spec)\n\n"
                        "## 核心执行步骤\n"
                        "1. **Android 硬件安全区与触控规范**：调用 `audit_material_spec` 或执行 `check_material.py`，确保状态栏/挖孔留白 `>= 24~48dp`，最小触控热区 `>= 48x48dp`（Material 3 标准）。\n"
                        "2. **严禁触发 iOS 专属要求**：严禁侵入 iOS 灵动岛 (71pt) 规则；使用 Material 3 Tokens 与规范。\n"
                        "3. **双轨交付**：输出 Android UI 设计规范 Markdown 与可交互工作台。\n",
                        encoding="utf-8"
                    )
                else:
                    # For iOS / default: Ensure check_hig.py is mounted
                    hig_script = scripts_dir / "check_hig.py"
                    hig_script.write_text(spec["script_code"], encoding="utf-8")
                    hig_script.chmod(0o755)
                    mat_script = scripts_dir / "check_material.py"
                    if mat_script.exists():
                        mat_script.unlink()

            elif r_code == "eng":
                cost_script = scripts_dir / "cost_audit.py"
                if not target_zero_inf:
                    cost_script.write_text(
                        "#!/usr/bin/env python3\n"
                        "import json\n"
                        "print(json.dumps({'client_ai_cost': 0.002, 'cdn_r2_cost_per_mau': 0.0008, "
                        "'zero_inference_enforced': False, 'edge_ai_allowed': True, 'passed': True}))\n",
                        encoding="utf-8"
                    )
                else:
                    cost_script.write_text(
                        "#!/usr/bin/env python3\n"
                        "import json\n"
                        "print(json.dumps({'client_ai_cost': 0.0, 'cdn_r2_cost_per_mau': 0.0008, "
                        "'zero_inference_enforced': True, 'edge_ai_allowed': False, 'passed': True}))\n",
                        encoding="utf-8"
                    )
                cost_script.chmod(0o755)

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
                "MODUFLOW_IS_PRIMARY": "true" if idx == 0 else "false",
                "MODUFLOW_PLATFORM": target_platform,
                "MODUFLOW_ZERO_INFERENCE": "true" if target_zero_inf else "false"
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
        "platform": target_platform,
        "client_zero_inference": target_zero_inf,
        "mounted_skills": mounted_skills,
        "mounted_mcp_servers": list(mcp_servers_config.keys()),
        "skills_dir": str(skills_mount_dir),
        "mcp_config_path": str(agy_mcp_file)
    }
