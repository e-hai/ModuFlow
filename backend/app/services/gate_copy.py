"""把关确认单上给人看的句子。机器字段仍留在证据里，不在这里决定放行。"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

ROLE_NAMES = {
    "mr": "市场研究",
    "ba": "商业分析",
    "pm": "产品",
    "mkt": "增长",
    "ux": "设计",
    "eng": "研发",
    "qa": "测试",
    "ops": "运营",
    "cmp": "合规",
    "lead": "项目总控",
}

FLAG_NAMES = {
    "payment": "真实收款或改价",
    "privacy": "用户隐私",
    "user_data": "用户数据",
    "encryption": "密钥或加密",
    "modify_lead_permissions": "权限改动",
    "public_statement": "对外公开发布",
    "compliance_high_risk": "重大合规风险",
    "budget_exceeded": "预算超支",
    "data_dictionary_schema_change": "数据结构调整",
}


def _usd(value: float) -> str:
    number = float(value)
    if abs(number) >= 10000:
        text = f"{number / 10000:.1f}".rstrip("0").rstrip(".")
        return f"{text} 万美元"
    if abs(number) >= 100:
        return f"{number:,.0f} 美元"
    return f"{number:.2f} 美元"


def _count(value: float) -> str:
    number = int(value)
    if number >= 10000:
        text = f"{number / 10000:.1f}".rstrip("0").rstrip(".")
        return f"{text} 万"
    return f"{number:,}"


def _pct(value: float) -> str:
    number = float(value)
    if number <= 1:
        number *= 100
    return f"{number:.1f}".rstrip("0").rstrip(".") + "%"


def _source(audit: Dict[str, Any]) -> str:
    text = str(audit.get("source") or "").strip()
    if len(text) > 80:
        return text[:80].rstrip() + "…"
    return text or "报告里注明的来源"


def _clean(value: Any, limit: int = 180) -> str:
    text = str(value or "").strip().strip("`").strip()
    if len(text) >= 2 and text[0] in "\"“" and text[-1] in "\"”":
        text = text[1:-1].strip()
    text = re.sub(r"\s+", " ", text).strip(" 。")
    if len(text) > limit:
        return text[:limit].rstrip() + "…"
    return text


def _blob(texts: List[str]) -> str:
    return "\n".join(texts or [])


def _loose_fields(texts: List[str]) -> Dict[str, Any]:
    from backend.app.services.deliverable_audit import merged_fields
    return merged_fields(texts or [])


def _uvp_sentence(fields: Dict[str, Any], blob: str) -> str:
    raw = fields.get("uvp")
    if isinstance(raw, str) and len(_clean(raw)) >= 8:
        return _clean(raw)
    match = re.search(r"核心价值主张[^\n：:]{0,20}[：:]\s*(.{8,160})", blob)
    if match:
        return _clean(match.group(1))
    match = re.search(r"(?:UVP|价值主张)[^\n：:]{0,20}[：:]\s*[“\"]?(.{8,160})", blob)
    return _clean(match.group(1)) if match else ""


def _hypotheses(blob: str) -> List[str]:
    rows = re.findall(r"\|\s*(H[1-4])\s*\|\s*([^|\n]+)", blob)
    if rows:
        return [f"{code}：{_clean(text, 80)}" for code, text in rows]
    packed = re.search(
        r"H1\s+([^、]{2,40})、\s*H2\s+([^、]{2,40})、\s*H3\s+([^、]{2,40})、\s*H4\s+([^）\n]{2,40})",
        blob,
    )
    if packed:
        return [f"H{index}：{_clean(packed.group(index), 40)}" for index in range(1, 5)]
    found: List[str] = []
    seen = set()
    for code, text in re.findall(r"(?<![~～])(H[1-4])\s+([^、，,\n）)]{4,40})", blob):
        if code in seen:
            continue
        seen.add(code)
        found.append(f"{code}：{_clean(text, 40)}")
    return found


def _choice_lines(blob: str) -> List[str]:
    choices: List[str] = []
    for line in re.findall(r"需拍板[：:]\s*(.+)", blob):
        cleaned = _clean(line, 160)
        if cleaned:
            choices.append(cleaned)
    for title, body in re.findall(
        r"-\s*\[\s*\]\s*(?:\*\*)?([^：:\n*]{2,40})(?:\*\*)?[：:]\s*(.+)",
        blob,
    ):
        cleaned = _clean(f"{title}：{body}", 180)
        if cleaned:
            choices.append(cleaned)
    return choices[:4]


def _cut_and_keep(blob: str) -> tuple:
    wont = re.search(r"\|\s*Won't\s*\|\s*([^|\n]+)", blob)
    must = re.search(r"\|\s*Must\s*\|\s*([^|\n]+)", blob)
    cut = _clean(wont.group(1), 80) if wont else ""
    keep = _clean(must.group(1), 80) if must else ""
    if not cut:
        match = re.search(r"坚决砍(?:掉|除)([^。；\n]{4,60})", blob)
        cut = _clean(match.group(1), 80) if match else ""
    if not keep:
        match = re.search(r"MVP 仅做([^；。\n]{4,80})", blob)
        keep = _clean(match.group(1), 80) if match else ""
    return keep, cut


def build_stage_brief(module_code: str, texts: List[str], audit: Dict[str, Any]) -> Dict[str, Any]:
    """Agent 交给项目总控的一页。decision 是您要拍板的那句话，缺了就不能交确认单。"""
    code = str(module_code)
    blob = _blob(texts)
    fields = _loose_fields(texts) if texts else {}
    decision = ""
    facts: List[str] = []
    choices: List[str] = []
    watch = ""
    missing: List[str] = []

    if code == "01":
        som = audit.get("first_year_som_usd")
        installs = audit.get("annual_target_installs")
        verdict = str(audit.get("verdict") or "")
        action = "盘子偏小，先控制投入" if "CAUTION" in verdict else "建议先做"
        if som is not None and installs is not None:
            installs_text = _count(installs)
            installs_text = f"{installs_text}次" if installs_text.endswith("万") else f"{installs_text} 次"
            decision = f"{action}。首年能拿到的现实盘子大约 {_usd(som)}（约 {installs_text}安装）。"
            facts = [
                f"盘子大约 {_usd(som)}，是用月搜索量、能拿到的比例和客单价算出来的。",
                f"数字来源：{_source(audit)}。",
            ]
        else:
            missing.append("首年盘子和安装量")
        watch = "定价还没定，下一关单独请您看。"
    elif code == "02":
        ratio = audit.get("ltv_cac_ratio")
        cac = audit.get("blended_cac_usd")
        ltv = audit.get("ltv_180d_usd")
        if ratio is not None:
            money = f"获客成本 {_usd(cac)}，180 天客户价值 {_usd(ltv)}。" if cac is not None and ltv is not None else ""
            decision = f"每花 1 美元获客，大约能收回 {ratio} 美元。{money}".strip()
            facts = [f"回收倍数 {ratio}，按 3 倍作为健康线。"]
            ladder = fields.get("price_ladder") or fields.get("pricing_ladder")
            if isinstance(ladder, str) and ladder.strip():
                facts.append(_clean(ladder, 160))
        else:
            missing.append("回收倍数")
        watch = "这里定下的价格，后面的工序不能自行改。"
    elif code == "03":
        uvp = _uvp_sentence(fields, blob)
        hypotheses = _hypotheses(blob)
        keep, cut = _cut_and_keep(blob)
        choices = _choice_lines(blob)
        if uvp:
            decision = f"是否按这个方向立项：{uvp}。"
        else:
            missing.append("一句话方向")
        if hypotheses:
            facts.append("要验证的假设：" + "；".join(hypotheses) + "。")
        else:
            missing.append("至少一条要验证的假设")
        if keep:
            facts.append(f"第一版留下：{keep}。")
        if cut:
            facts.append(f"明确不做：{cut}。")
        watch = "后面的小额测试和需求都按这个方向做。"
    elif code == "04":
        budget = fields.get("test_budget_usd")
        if budget in (None, ""):
            match = re.search(r"测试预算[：:]\s*\$?\s*([0-9]+(?:\.[0-9]+)?)", blob)
            budget = float(match.group(1)) if match else None
        hypotheses = _hypotheses(blob)
        if budget not in (None, ""):
            decision = f"用 {_usd(float(budget))} 做小额测试。实测还没回来，不能当成已经验证。"
            facts.append(f"测试预算 {_usd(float(budget))}。")
        else:
            decision = "做一个可点击的测试页。实测还没回来，不能当成已经验证。"
            missing.append("测试预算")
        if hypotheses:
            facts.append("这页要验证：" + "；".join(hypotheses[:4]) + "。")
        choices = _choice_lines(blob)
        watch = "外测数字必须来自真实埋点，不能在报告里编造。"
    elif code == "05":
        match = re.search(r"本版只交付([^。\n]+)", blob)
        if match:
            decision = f"这版只交付{_clean(match.group(1), 120)}。"
        else:
            score = audit.get("score")
            score_text = f"清单评分 {score}。" if score is not None else ""
            decision = f"需求规格已按清单写全。{score_text}".strip()
            missing.append("这版做哪些")
        facts.append("范围、页面、业务规则、埋点和验收写在同一份规格里。")
        watch = "封版之后要改范围，走变更，不在下游稿里直接改。"
    elif code == "06":
        platform = audit.get("platform") or "ios"
        if platform == "cross_platform":
            decision = "iOS 和 Android 的安全区、按钮尺寸都达到了各自的最低要求。"
            facts = ["两端都要过：iOS 看留白和 44pt 按钮，Android 看状态栏避让和 48dp 按钮。"]
        elif platform == "android":
            decision = "Android 的状态栏避让和按钮尺寸达到了要求。"
            facts = ["没有去套 iOS 的规则。"]
        else:
            decision = "iOS 的顶部留白和按钮尺寸达到了要求。"
            facts = ["按 iOS 的安全区核对。"]
        watch = "和需求冲突的地方回到需求变更，设计稿里不直接改业务规则。"
    elif code == "07":
        coverage = (audit.get("coverage") or {}).get("coverage_percent", audit.get("coverage_percent"))
        inference = audit.get("inference") or {}
        zero = inference.get("zero_client_ai_compliant")
        cover_text = f"核心逻辑的测试覆盖了 {coverage:.0f}%。" if isinstance(coverage, (int, float)) else "核心逻辑的测试覆盖率已写明。"
        infer_text = "手机安装包里没有做模型推理。" if zero else "推理方式已按本项目的约定核对。"
        decision = f"{cover_text}{infer_text}"
        facts = [cover_text, infer_text]
        watch = "能不能发布，还要等测试阶段确认。"
    elif code == "08":
        p0 = int(audit.get("open_p0") or 0)
        p1 = int(audit.get("open_p1") or 0)
        decision = f"还剩严重问题 {p0} 个、主要问题 {p1} 个。"
        facts = [decision]
        watch = "还有严重或主要问题没关时，不能带着进入发布。"
    elif code == "09":
        decision = "发布材料里写了合规说明、出问题时怎么降级，以及怎么回滚。商店提审要您签字。"
        facts = ["严重问题和主要问题已清零，并写了远程降级开关。"]
        watch = "没有您的签字，不能提交商店。"
    elif code == "10":
        ecac = audit.get("ecac_usd")
        limit = audit.get("ecac_limit_usd")
        if ecac is not None and limit is not None:
            decision = f"预计获客成本 {_usd(ecac)}，熔断线 {_usd(limit)}。"
            facts = [f"成本没有超过熔断线 {_usd(limit)}。" if float(ecac) <= float(limit) else f"成本已经超过熔断线 {_usd(limit)}。"]
        else:
            decision = "获客方案写了成本和熔断线。"
            missing.append("预计获客成本和熔断线")
        watch = "成本超过熔断线就停，不能改口径继续花。"
    elif code == "11":
        if audit.get("d1_retention") is not None:
            decision = (
                f"次日留存 {_pct(audit['d1_retention'])}，7 日 {_pct(audit['d7_retention'])}，"
                f"30 日 {_pct(audit['d30_retention'])}。"
            )
            facts = ["下一版建议写了对应的留存或流失依据。"]
        else:
            decision = "运营复盘给出了留存和下一版建议。"
            missing.append("次日、7 日、30 日留存")
        watch = "运营只提建议，不能直接改线上版本或预算。"
    else:
        missing.append("这一关要您确认的那句话")

    if audit.get("passed") is False:
        missing = []
    return {
        "decision": decision,
        "facts": [fact for fact in facts if fact],
        "choices": choices,
        "watch": watch,
        "missing": missing,
    }


def render_stage_brief(brief: Dict[str, Any]) -> Dict[str, str]:
    facts = [fact for fact in brief.get("facts") or [] if fact]
    choices = [choice for choice in brief.get("choices") or [] if choice]
    watch = str(brief.get("watch") or "").strip()
    risk_parts: List[str] = []
    if choices:
        risk_parts.append("请您选：\n" + "\n".join(f"- {choice}" for choice in choices))
    if watch:
        risk_parts.append(watch)
    return {
        "recommendation": str(brief.get("decision") or "请确认是否放行。"),
        "evidence": "\n".join(facts),
        "risk": "\n".join(risk_parts),
    }


def describe_passed_stage(module_code: str, module_name: str, audit: Dict[str, Any]) -> Dict[str, str]:
    """已通过检查的工序，生成确认单上的结论、依据和风险。"""
    brief = audit.get("brief")
    if not isinstance(brief, dict) or not brief.get("decision"):
        brief = build_stage_brief(module_code, [], audit)
    if brief.get("decision"):
        return render_stage_brief(brief)
    code = str(module_code)
    if code == "01":
        som = audit.get("first_year_som_usd")
        installs = audit.get("annual_target_installs")
        verdict = str(audit.get("verdict") or "")
        action = "盘子偏小，先控制投入" if "CAUTION" in verdict else "建议先做"
        if som is not None and installs is not None:
            installs_text = _count(installs)
            installs_text = f"{installs_text}次" if installs_text.endswith("万") else f"{installs_text} 次"
            recommendation = (
                f"{action}。按这份市场研究，首年能拿到的现实盘子大约 {_usd(som)}"
                f"（约 {installs_text}安装）。数字写了来源。请确认是否按这个结论进入定价测算。"
            )
            evidence = (
                f"首年能拿到的盘子大约 {_usd(som)}，是用月搜索量、能拿到的比例和客单价算出来的，不是一个空的大盘。\n"
                f"关键数字的来源：{_source(audit)}。\n"
                f"结论写明了{action}。"
            )
        else:
            recommendation = f"{module_name}已写明做不做，并附了盘子测算和来源。请确认是否进入定价测算。"
            evidence = "报告里有自下而上的盘子、做不做的结论，以及数字来源。"
        risk = "这一关没有要您现在拍板的花钱、隐私、密钥或改价事项。定价还没定，下一关会单独请您看。"
        return {"recommendation": recommendation, "evidence": evidence, "risk": risk}

    if code == "02":
        ratio = audit.get("ltv_cac_ratio")
        cac = audit.get("blended_cac_usd")
        ltv = audit.get("ltv_180d_usd")
        if ratio is not None:
            recommendation = (
                f"每花 1 美元获客，大约能收回 {ratio} 美元"
                + (f"（获客成本 {_usd(cac)}，180 天客户价值 {_usd(ltv)}）" if cac is not None and ltv is not None else "")
                + "。请确认这套定价能不能做。"
            )
            evidence = f"回收倍数 {ratio}，按 3 倍作为健康线来看。"
        else:
            recommendation = "定价和回收测算已经写好。请确认这套定价能不能做。"
            evidence = "单位经济测算已写进交付物。"
        risk = "这里定的是价格和获客成本，请您看过再放行。后面的工序不能自行改这里定下的价格。"
        return {"recommendation": recommendation, "evidence": evidence, "risk": risk}

    if code == "03":
        return {
            "recommendation": "方向卡已写清卖点，并列出要验证的关键假设。请确认这个方向是否立项。",
            "evidence": "有价值主张，也有第一条要验证的假设。",
            "risk": "方向一旦定下，后面的验证和需求都按这张卡走。",
        }
    if code == "04":
        return {
            "recommendation": "假门页面已经能打开、能点击。真实外测数据还没回来之前，不能当成已经验证。请确认是否按这个方案做小额测试。",
            "evidence": "有一个可点击的测试页。实测点击和留资要等真人测试回填，报告里不应编造。",
            "risk": "这里要花一笔小额测试费，金额要落在这一阶段的授权额度里。",
        }
    if code == "05":
        score = audit.get("score")
        score_text = f"（清单评分 {score}）" if score is not None else ""
        return {
            "recommendation": f"需求规格已按清单写全{score_text}。请确认这版范围可以封版。",
            "evidence": "范围、页面、业务规则、埋点和验收都写在同一份规格里，没有把建表和接口写进来。",
            "risk": "封版之后，设计和研发按这份规格做。要改范围，走变更，不在下游稿里直接改。",
        }
    if code == "06":
        platform = audit.get("platform") or "ios"
        if platform == "cross_platform":
            evidence = "iOS 和 Android 的安全区、按钮尺寸都达到了各自的最低要求。"
        elif platform == "android":
            evidence = "Android 的状态栏避让和按钮尺寸达到了要求，没有去套 iOS 的规则。"
        else:
            evidence = "iOS 的顶部留白和按钮尺寸达到了要求。"
        return {
            "recommendation": "设计稿的安全区和按钮尺寸已经核对过。请确认可以交给研发。",
            "evidence": evidence,
            "risk": "设计不能自行改业务规则。和规格冲突的地方应回到需求变更。",
        }
    if code == "07":
        coverage = (audit.get("coverage") or {}).get("coverage_percent", audit.get("coverage_percent"))
        inference = audit.get("inference") or {}
        zero = inference.get("zero_client_ai_compliant")
        cover_text = f"核心逻辑的测试覆盖了 {coverage:.0f}%。" if isinstance(coverage, (int, float)) else "核心逻辑的测试覆盖率已写明。"
        infer_text = "手机安装包里没有做模型推理。" if zero else "推理方式已按本项目的约定核对。"
        return {
            "recommendation": "研发交付里的测试覆盖和推理约定已经核对过。请确认可以交给测试。",
            "evidence": f"{cover_text}{infer_text}",
            "risk": "研发通过只说明工程就绪，能不能发布仍要等测试阶段确认。",
        }
    if code == "08":
        return {
            "recommendation": "阻断上线的严重问题和主要问题都已清掉。请确认这版质量可以进入发布准备。",
            "evidence": f"未关闭的严重问题 {int(audit.get('open_p0') or 0)} 个，主要问题 {int(audit.get('open_p1') or 0)} 个。",
            "risk": "还有严重或主要问题没关时，不能带着上线。",
        }
    if code == "09":
        return {
            "recommendation": "发布材料里有合规说明、出问题时的降级办法和回滚计划。商店提审必须由您签字，系统不会代签。",
            "evidence": "严重问题和主要问题已清零，并写了远程降级开关。",
            "risk": "没有您的签字，这一关不能放行，也不能提交商店。",
        }
    if code == "10":
        ecac = audit.get("ecac_usd")
        limit = audit.get("ecac_limit_usd")
        if ecac is not None and limit is not None:
            evidence = f"预计获客成本 {_usd(ecac)}，没有超过熔断线 {_usd(limit)}。"
        else:
            evidence = "获客成本和熔断线已写进方案。"
        return {
            "recommendation": "获客方案写了成本和熔断线。首次买量或新国家投放，请您确认预算。",
            "evidence": evidence,
            "risk": "成本一旦超过熔断线，投放应停，不能靠改口径继续花。",
        }
    if code == "11":
        if audit.get("d1_retention") is not None:
            evidence = (
                f"次日留存 {_pct(audit['d1_retention'])}，7 日 {_pct(audit['d7_retention'])}，"
                f"30 日 {_pct(audit['d30_retention'])}。下一版需求写了对应的留存或流失依据。"
            )
        else:
            evidence = "留存数字和下一版需求都写了依据。"
        return {
            "recommendation": "运营复盘给出了留存情况和下一版建议。请确认是否把建议交回需求环节。",
            "evidence": evidence,
            "risk": "运营只提建议，不能直接改线上版本或预算。",
        }
    return {
        "recommendation": f"{module_name}的结论已经写好。请确认是否放行。",
        "evidence": "这一关要求的结论和依据都已写进交付物。",
        "risk": "没有发现要单独升级请您处理的敏感事项。",
    }


def flag_note(flags: List[str]) -> str:
    names = [FLAG_NAMES.get(flag, flag) for flag in flags]
    if not names:
        return ""
    return "交付物里标出了需要您知道的事项：" + "、".join(names) + "。这些事项要您看过才能过。"


def compliance_note(compliance: Optional[Dict[str, Any]]) -> str:
    if not compliance:
        return ""
    status = compliance.get("status")
    if status == "passed":
        return "合规初筛没有发现要停下来的问题。"
    if status == "needs_fix":
        return "合规初筛还有要改的地方，改完才能继续。"
    return "合规认为这件事需要法务看过才能继续。"


def review_note(
    reviews: List[Dict[str, Any]],
    overridden_by: Optional[str] = None,
    change_requests: Optional[List[Dict[str, Any]]] = None,
) -> str:
    if overridden_by:
        return f"您已决定按当前稿继续，这次复核意见不挡住放行（{overridden_by}）。"
    parts = []
    for review in reviews or []:
        who = ROLE_NAMES.get(str(review.get("reviewer") or ""), str(review.get("reviewer") or "同事"))
        verdict = review.get("verdict")
        if verdict == "approve":
            parts.append(f"{who}看过，认为可以继续")
        elif verdict == "request_changes":
            parts.append(f"{who}要求再改一版")
        elif verdict == "raise_cr":
            parts.append(f"{who}另外提了变更")
        else:
            parts.append(f"{who}已复核")
    text = ("同事复核：" + "；".join(parts) + "。") if parts else ""
    escalated = [item for item in (change_requests or []) if item.get("escalated")]
    parked = [item for item in (change_requests or []) if not item.get("escalated")]
    if escalated:
        text += "其中有需要您裁决的变更。"
    elif parked:
        text += "另有变更已记下，不挡住这一关。"
    return text
