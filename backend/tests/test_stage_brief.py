"""确认单必须引用交付物里要拍板的那句话，不能只写「材料齐了」。"""

from backend.app.services.deliverable_audit import audit_stage
from backend.app.services.gate_copy import describe_passed_stage
from backend.app.services.lead_service import compose_lead_rationale
from backend.app.services.simulator_deliverables import _direction


def test_direction_brief_quotes_the_sentence():
    text = """
uvp: "口袋里的自律神经重置器：60秒静音触觉呼吸，零等待、零打扰、即开即吸。"
核心价值主张 (UVP)：口袋里的自律神经重置器。
MVP 仅做 60 秒触觉呼吸。
坚决砍除长音频、社群和账号。
向工序 04 移交假设（H1 视觉钩子 CTR ≥4.2%、H2 即用转化 ≥12%）。
- [ ] **启动方式**：打开就进入呼吸，或先选模式。
"""
    audit = audit_stage("03", [text])
    assert audit["passed"], audit["reasons"]
    sheet = describe_passed_stage("03", "产品方向决策", audit)
    assert "口袋里的自律神经重置器" in sheet["recommendation"]
    assert "方向卡已写清卖点" not in sheet["recommendation"]
    assert "H1" in sheet["evidence"]
    assert "请您选" in sheet["risk"]
    assert "打开就进入呼吸" in sheet["risk"]


def test_direction_without_a_sentence_cannot_be_submitted():
    audit = audit_stage("03", ["这里有价值主张，也写了 H1，但没有具体方向。"])
    assert audit["passed"] is False
    assert any("一句话方向" in reason for reason in audit["reasons"])


def test_simulator_direction_still_passes():
    audit = audit_stage("03", [_direction("演示")])
    assert audit["passed"], audit["reasons"]
    sheet = describe_passed_stage("03", "产品方向决策", audit)
    assert "10 秒内获得结果" in sheet["recommendation"]


def test_lead_speaks_in_the_first_person_and_quotes_the_blocker():
    code, text = compose_lead_rationale(
        escalated=False,
        escalation_reasons=[],
        blocking_findings=["用到了健康与生物识别：需求里还没写清为什么需要。"],
    )
    assert code == "rejected"
    assert text.startswith("我看完了")
    assert "健康与生物识别" in text
    assert "建议先别过" in text
