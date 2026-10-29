"""
Compliance & Risk Specialist (cmp) Engine
(backend/app/services/compliance_engine.py)

Covers:
1. Three core compliance checkpoints:
   - Stage 03 (Product Direction): Privacy & data flow preliminary screening, regional payment & tax hints, trademark/IP infringement check.
   - Stage 05 (PRD Requirements): Sensitive data classification, dark patterns avoidance, ATT tracking prompt rules.
   - Stage 09 (Release & Submission): Apple App Store Review Guidelines (4.3 spam, 5.1 privacy policy), Remote Config kill switch, rollback plan.
2. Structured output: status in ['passed', 'needs_fix', 'legal_review'], risk_level in ['low', 'medium', 'high'].
3. High risk rule: high-risk compliance findings automatically escalate gate to 🔴 G5 (human approval required).
4. Strict Redline: Never produces formal legal warranties; always includes mandatory legal disclaimer.
5. All compliance evaluations are audited into physical decisions/ directory.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from backend.app.core.config import settings
from backend.app.models.entities import (
    Product,
    WorkflowRun,
    ModuleInstance,
    Artifact,
    GateApplication,
    ExecutiveRisk
)


LEGAL_DISCLAIMER = (
    "【免责声明】：本报告由合规风控智能体 (cmp) 依据各大应用商店开发者政策与常规合规准则出具，"
    "仅作为项目工程与风险排查参考，不构成任何具有法律效力的正式法律意见。"
    "高风险问题必须由签约法务顾问或执业律师出具正式书面结论。"
)

# Rule keywords for Stage 03
SENSITIVE_PERMISSIONS = [
    ("精准地理位置", ["location", "gps", "精准定位", "地理位置", "后台定位"]),
    ("通讯录与联系人", ["contacts", "address_book", "通讯录", "联系人"]),
    ("相册全量访问", ["photo_library", "all_photos", "相册权限", "全量照片"]),
    ("麦克风后台监听", ["microphone", "record_audio", "麦克风", "录音"]),
    ("健康与生物识别", ["health_data", "biometric", "face_id", "生物识别", "健康数据"]),
]

REGIONAL_TAX_RULES = {
    "欧盟": {
        "hints": [
            "欧盟 DAC7 税务指令：平台需向成员国税务机关报告创作者与卖方交易收入；",
            "增值税 (VAT OSS)：数字服务增值税率 19%~27%，需按消费国属地申报代缴；",
            "GDPR 严苛数据合规：Cookie/数据收集必须提供显式 Reject All 按钮，禁止默认勾选。"
        ]
    },
    "欧洲": {
        "hints": [
            "欧盟 DAC7 税务指令：需按属地向税务机关报备开发者收益；",
            "增值税 (VAT OSS)：数字服务增值税率 19%~27%，需按消费国属地申报代缴；",
            "GDPR 严苛隐私合规：涉及跨境数据传输需具备标准合同条款 (SCC)。"
        ]
    },
    "美国": {
        "hints": [
            "美区经济联结 (Economic Nexus)：各州对超过 $100k 或 200 笔交易征收州销售税 (Sales Tax)；",
            "COPPA 儿童隐私法规：13 岁以下用户严禁收集未经验证家长同意的个人信息；",
            "加州 CCPA/CPRA：必须在设置中提供 'Do Not Sell My Personal Information' 明确选项。"
        ]
    },
    "日韩": {
        "hints": [
            "日本《资金决济法》与特定商交易法：代币/虚拟金币需标注有效期限与退款限制；",
            "韩国电信业务法修正案：禁止强制绑定单一应用内购买 (IAP)，允许第三方支付通道接入。"
        ]
    },
    "东南亚": {
        "hints": [
            "印尼/越南/泰国本地数据留存法规 (Data Localization)：部分金融支付日志需本地存储；",
            "本地电子钱包 (GrabPay, MoMo, PromptPay) 结算与预扣税 (WHT) 规则。"
        ]
    }
}


def audit_stage_compliance(
    stage_code: str,
    content: str,
    target_market: str = "global",
    platform: str = "all",
    manifest: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Audits deliverable text for stage 03, 05, or 09.
    Returns:
        {
            "stage_code": str,
            "status": "passed" | "needs_fix" | "legal_review",
            "risk_level": "low" | "medium" | "high",
            "is_g5_escalated": bool,
            "findings": List[Dict],
            "regional_tax_hints": List[str],
            "summary": str,
            "legal_disclaimer": str
        }
    """
    content_lower = content.lower()
    findings: List[Dict[str, Any]] = []
    status = "passed"
    risk_level = "low"
    regional_hints: List[str] = []

    # =========================================================================
    # Checkpoint 1: Stage 03 - 立项初筛合规
    # =========================================================================
    if stage_code == "03":
        # 1.1 Privacy & Sensitive Permissions
        for perm_name, kws in SENSITIVE_PERMISSIONS:
            if any(k in content_lower for k in kws):
                findings.append({
                    "category": "privacy_data_flow",
                    "item": f"高敏感系统权限申请: {perm_name}",
                    "severity": "medium",
                    "passed": False,
                    "advice": f"立项检测到涉及【{perm_name}】。必须在工序 05 PRD 中明确最小可用原则与用户授权理由，否则将遭遇平台拒审。"
                })
                if risk_level == "low":
                    risk_level = "medium"
                    status = "needs_fix"

        # 1.2 Regional Tax & Payment Hints
        matched_regions = [r for r in REGIONAL_TAX_RULES if r in target_market]
        if not matched_regions:
            matched_regions = ["美国", "欧盟"] # Default出海基准

        for reg in matched_regions:
            regional_hints.extend(REGIONAL_TAX_RULES[reg]["hints"])

        findings.append({
            "category": "regional_tax_payment",
            "item": f"目标出海市场 ({', '.join(matched_regions)}) 税务与变现提示",
            "severity": "info",
            "passed": True,
            "advice": "已出具目标区域支付税务参考清单，支持工序 02 定价与工序 04 外测。"
        })

        # 1.3 Trademark & IP check (e.g. gambling, deceptive claims, blatant trademark infringement)
        high_risk_words = ["赌博", "博彩", "包赚", "casino", "100%返现", "稳赚不赔", "破解版", "cracked"]
        if any(w in content_lower for w in high_risk_words):
            findings.append({
                "category": "platform_policy",
                "item": "涉嫌赌博、虚假收益承诺或版权高危词",
                "severity": "high",
                "passed": False,
                "advice": "严禁出现赌博机制或虚假收益承诺，触碰 Apple 4.3/Google Play 违规红线，必须交由法务评估！"
            })
            risk_level = "high"
            status = "legal_review"

    # =========================================================================
    # Checkpoint 2: Stage 05 - PRD 规格合规
    # =========================================================================
    elif stage_code == "05":
        # 2.1 Sensitive Data Security & Encryption
        if "password" in content_lower or "密码" in content_lower or "token" in content_lower:
            if "明文" in content_lower or "plaintext" in content_lower:
                findings.append({
                    "category": "privacy_data_flow",
                    "item": "明文存储密码或敏感凭证",
                    "severity": "high",
                    "passed": False,
                    "advice": "严禁在本地 SQLite 或日志中明文存储密码与 Token，必须声明安全哈希或 Keychain/Keystore 加密机制！"
                })
                risk_level = "high"
                status = "legal_review"
            else:
                findings.append({
                    "category": "privacy_data_flow",
                    "item": "敏感凭证数据字典规范",
                    "severity": "low",
                    "passed": True,
                    "advice": "数据字典已包含敏感凭证，请工序 07 研发严格使用系统安全存储 (Keychain/EncryptedSharedPreferences)。"
                })

        # 2.2 Dark Patterns / Auto-renew subscription
        if "订阅" in content_lower or "subscription" in content_lower:
            if not any(k in content_lower for k in ["取消", "退款", "cancel", "refund"]):
                findings.append({
                    "category": "regional_tax_payment",
                    "item": "暗黑模式规避: 缺少明确退款与取消自动续费指引",
                    "severity": "medium",
                    "passed": False,
                    "advice": "PRD 必须显式规定订阅管理、自动续费提示与用户主动退款通道，避免违反 Apple 3.1.2 准则。"
                })
                if risk_level == "low":
                    risk_level = "medium"
                    status = "needs_fix"

        # 2.3 Platform-specific Tracking. A manifest owns this check; prose keywords are the fallback.
        norm_platform = (platform or "all").lower()
        from backend.app.services.delivery_contract import stage_code as _stage_code
        from backend.app.services.delivery_contract import tracking_findings
        from backend.app.services.profile_guard import covers_android, covers_ios
        manifest_owns_tracking = (
            manifest is not None and _stage_code(manifest.get("stage")) == "05"
        )
        if manifest_owns_tracking:
            for finding in tracking_findings(manifest, norm_platform):
                findings.append(finding)
                if not finding.get("passed") and risk_level == "low":
                    risk_level = "medium"
                    status = "needs_fix"
        elif covers_ios(norm_platform):
            uses_att = any(key in content_lower for key in ("idfa", "广告追踪", "att"))
            if uses_att:
                missing = []
                if not any(key in content_lower for key in (
                    "nsusertrackingusagedescription", "授权弹窗文案", "att 授权弹窗文案",
                )):
                    missing.append("原生授权弹窗文案")
                if not (
                    any(key in content_lower for key in ("denied", "拒绝追踪", "ask app not to track"))
                    and "降级" in content_lower
                ):
                    missing.append("用户拒绝后的降级分支")
                findings.append({
                    "category": "platform_policy",
                    "item": "Apple App Tracking Transparency (ATT) 弹窗规格",
                    "severity": "medium" if missing else "info",
                    "passed": not missing,
                    "advice": (
                        "ATT 授权文案与拒绝后的降级分支已在 PRD 中声明。"
                        if not missing else
                        f"如需采集 IDFA 进行跨应用广告归因，请补充：{'、'.join(missing)}。"
                    ),
                })
                if missing and risk_level == "low":
                    risk_level = "medium"
                    status = "needs_fix"
        if not manifest_owns_tracking and covers_android(norm_platform):
            uses_ad_id = any(key in content_lower for key in ("广告追踪", "ad_id", "gaid", "advertising id"))
            if uses_ad_id:
                missing = []
                if not any(key in content_lower for key in (
                    "com.google.android.gms.permission.ad_id", "ad_id 权限", "广告标识符 (`ad_id`)",
                )):
                    missing.append("AD_ID 权限声明")
                if not any(key in content_lower for key in (
                    "家庭政策", "families policy", "目标受众年龄", "13 岁及以上", "13+",
                )):
                    missing.append("家庭政策或目标受众声明")
                if not (
                    any(key in content_lower for key in (
                        "停用个性化广告", "opted_out", "opt out", "删除广告 id",
                    ))
                    and "降级" in content_lower
                ):
                    missing.append("用户停用广告标识符后的降级分支")
                findings.append({
                    "category": "platform_policy",
                    "item": "Google Play Advertising ID (AD_ID) 权限声明与家庭政策",
                    "severity": "medium" if missing else "info",
                    "passed": not missing,
                    "advice": (
                        "AD_ID 权限、家庭政策与停用后的降级分支已在 PRD 中声明。"
                        if not missing else
                        f"如需使用 Google Play 广告标识符，请补充：{'、'.join(missing)}。"
                    ),
                })
                if missing and risk_level == "low":
                    risk_level = "medium"
                    status = "needs_fix"

    # =========================================================================
    # Checkpoint 3: Stage 09 - 提审上线合规
    # =========================================================================
    elif stage_code == "09":
        norm_platform = (platform or "all").lower()
        from backend.app.services.profile_guard import covers_android, covers_ios
        # 3.1 Store Policy & Spam/Copycat check
        if covers_android(norm_platform) and ("查重" in content_lower or "重复应用" in content_lower or "换皮" in content_lower):
            findings.append({
                "category": "platform_policy",
                "item": "Google Play 重复内容与抄袭政策排查 (Repetitive Content Policy)",
                "severity": "low",
                "passed": True,
                "advice": "提审包需具备独有 UVP 价值主张与差异化体验，严禁换皮打包违反 Google Play 政策。"
            })
        if covers_ios(norm_platform) and ("4.3" in content_lower or "查重" in content_lower or "重复应用" in content_lower):
            findings.append({
                "category": "platform_policy",
                "item": "Apple 4.3 查重度排查",
                "severity": "low",
                "passed": True,
                "advice": "提审包需具备独有 UVP 价值主张与差异化 UI 架构，严禁换皮打包。"
            })

        # 3.2 Privacy Policy URL check
        if not any(k in content_lower for k in ["privacy", "隐私协议", "隐私政策", "privacy_policy"]):
            findings.append({
                "category": "platform_policy",
                "item": "缺少应用商店提审隐私协议有效链接",
                "severity": "high",
                "passed": False,
                "advice": "Apple 5.1 与 Google Play 强制要求元数据包含可公开访问的隐私协议有效 URL，缺失将直接拒审！"
            })
            risk_level = "high"
            status = "legal_review"

        # 3.3 Remote Config & Rollback Plan
        has_remote_config = any(k in content_lower for k in ["remote config", "降级开关", "功能开关", "feature flag"])
        has_rollback = any(k in content_lower for k in ["回滚", "rollback", "应急预案", "降级预案"])

        if not has_remote_config or not has_rollback:
            findings.append({
                "category": "platform_policy",
                "item": "提审降级保护开关或回滚预案不完备",
                "severity": "medium",
                "passed": False,
                "advice": "发布门禁强制要求具备 Remote Config 提审降级开关与快速回滚预案，避免线上重大故障失控。"
            })
            if risk_level == "low":
                risk_level = "medium"
                status = "needs_fix"

    # Default passing finding if clean
    if not findings:
        findings.append({
            "category": "general",
            "item": "常规合规初筛检查",
            "severity": "info",
            "passed": True,
            "advice": "未检测到显著平台政策冲突或高危违规线索。"
        })

    is_g5_escalated = (risk_level == "high" or status == "legal_review")

    if is_g5_escalated:
        summary = f"🚨 合规风控发现高危隐患，已自动升级为 🔴 G5 关口 (状态: {status})，必须由人类与法务复核放行。"
    elif status == "needs_fix":
        summary = f"⚠️ 合规风控发现 {len([f for f in findings if not f['passed']])} 项待改建议，请在工序基线中完善。"
    else:
        summary = f"✅ 工序 {stage_code} 合规风控检查通过，未发现阻断性平台政策风险。"

    return {
        "stage_code": stage_code,
        "status": status,
        "risk_level": risk_level,
        "is_g5_escalated": is_g5_escalated,
        "findings": findings,
        "regional_tax_hints": regional_hints,
        "summary": summary,
        "legal_disclaimer": LEGAL_DISCLAIMER
    }


COMPLIANCE_STAGES = ("03", "05", "09")


async def resolve_target_market(db: AsyncSession, product: Optional[Product]) -> str:
    if not product or not product.initiative_id:
        return "全球"
    from backend.app.models.entities import StrategicInitiative
    init_obj = (await db.execute(
        select(StrategicInitiative).where(StrategicInitiative.id == product.initiative_id)
    )).scalar_one_or_none()
    return (init_obj.target_market if init_obj and init_obj.target_market else None) or "全球"


async def audit_module_compliance(
    db: AsyncSession,
    module_code: str,
    product: Optional[Product],
    content: str,
    manifest: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """cmp checkpoint for stages 03/05/09; None for stages without a checkpoint."""
    if module_code not in COMPLIANCE_STAGES:
        return None
    return audit_stage_compliance(
        stage_code=module_code,
        content=content,
        target_market=await resolve_target_market(db, product),
        platform=(getattr(product, "platform", None) or "ios") if product else "ios",
        manifest=manifest,
    )


def compliance_failed_items(result: Dict[str, Any]) -> List[str]:
    return [
        f"[cmp {f.get('severity')}] {f.get('item')}：{f.get('advice')}"
        for f in result.get("findings") or []
        if not f.get("passed")
    ]


async def run_stage_compliance_check(
    db: AsyncSession,
    module_id: str
) -> Dict[str, Any]:
    """
    Executes compliance check on a specific ModuleInstance:
    1. Loads latest module deliverable content.
    2. Runs audit_stage_compliance.
    3. If high risk (G5): automatically escalates GateApplication to 🔴 RED and creates ExecutiveRisk.
    4. Writes audit log into decisions/ directory.
    """
    mod_stmt = select(ModuleInstance).where(ModuleInstance.id == module_id)
    res = await db.execute(mod_stmt)
    module = res.scalar_one_or_none()
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")

    run_stmt = select(WorkflowRun).where(WorkflowRun.id == module.run_id)
    run_res = await db.execute(run_stmt)
    run = run_res.scalar_one_or_none()
    product_id = run.product_id if run else None

    product = None
    if product_id:
        p_stmt = select(Product).where(Product.id == product_id)
        p_res = await db.execute(p_stmt)
        product = p_res.scalar_one_or_none()

    target_market = await resolve_target_market(db, product)
    init_id = product.initiative_id if product and product.initiative_id else "platform"

    # Load latest artifact content
    art_stmt = select(Artifact).where(Artifact.module_id == module_id).order_by(Artifact.version.desc())
    art_res = await db.execute(art_stmt)
    artifact = art_res.scalars().first()
    deliverable_text = artifact.content if artifact else f"工序 {module.name} 待审查草案"

    target_platform = "ios"
    if product:
        target_platform = getattr(product, "platform", "ios") or "ios"

    # Run compliance audit
    audit_res = audit_stage_compliance(
        stage_code=module.module_code,
        content=deliverable_text,
        target_market=target_market,
        platform=target_platform
    )

    now = datetime.now(timezone.utc)

    # If escalated to G5 -> escalate GateApplication and emit ExecutiveRisk
    if audit_res["is_g5_escalated"]:
        gate_stmt = select(GateApplication).where(GateApplication.module_id == module_id)
        gate_res = await db.execute(gate_stmt)
        gate = gate_res.scalar_one_or_none()
        if gate:
            gate.effective_level = "red"
            gate.is_escalated = True
            cur_reasons = list(gate.escalation_reasons or [])
            if "compliance_high_risk" not in cur_reasons:
                cur_reasons.append("compliance_high_risk")
            gate.escalation_reasons = cur_reasons
            gate.risk_assessment = (gate.risk_assessment or "") + f"\n[G5 合规自动升红] {audit_res['summary']}"
            db.add(gate)

        rule_code = f"COMPLIANCE_G5_{module.module_code}"
        existing_risk = (await db.execute(select(ExecutiveRisk).where(
            ExecutiveRisk.initiative_id == init_id,
            ExecutiveRisk.rule_code == rule_code,
            ExecutiveRisk.product_code == (product.code if product else None),
            ExecutiveRisk.is_resolved == False,  # noqa: E712
        ))).scalars().first()
        if existing_risk is None:
            db.add(ExecutiveRisk(
                initiative_id=init_id,
                rule_code=rule_code,
                title=f"🚨 G5 合规高危告警: 工序 {module.module_code} 触碰平台政策红线",
                severity="critical",
                description=audit_res["summary"],
                product_code=product.code if product else None,
                action_suggestion="请人类负责人组织法务审查，修改涉嫌违规的业务规格或元数据，严禁带病提审。",
                is_resolved=False
            ))

    # Persist audit record in physical decisions/ directory
    if product and product.initiative_id:
        decisions_dir = Path(settings.WORKSPACE_DIR) / product.initiative_id / "products" / product.code / "decisions"
        decisions_dir.mkdir(parents=True, exist_ok=True)
        ts_str = now.strftime("%Y%m%d_%H%M%S")
        log_file = decisions_dir / f"{ts_str}_compliance_audit_stage_{module.module_code}.json"
        log_file.write_text(json.dumps({
            "event": "COMPLIANCE_AUDIT",
            "timestamp": now.isoformat(),
            "module_id": module.id,
            "module_code": module.module_code,
            "module_name": module.name,
            "product_code": product.code,
            "audit_result": audit_res
        }, indent=2, ensure_ascii=False), encoding="utf-8")

    await db.commit()
    return audit_res
