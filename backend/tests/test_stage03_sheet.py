"""工序 03 确认单列出价值主张、使用人群、必做、明确不做和每条假设的验证方式。"""

import json

from backend.app.services.deliverable_audit import audit_stage
from backend.app.services.delivery_contract import RISK_FLAG_KEYS, validate_manifest
from backend.app.services.gate_copy import describe_passed_stage


def _direction():
    return {
        "uvp": "60 秒静音呼吸，打开就能用",
        "target_audience": "想在工位上立刻静下来的人",
        "moscow": {
            "must": ["60 秒呼吸", "结果保存"],
            "wont": ["长音频", "社群"],
        },
        "hypotheses": [
            {"id": "H1", "hypothesis": "愿意为无广告付费", "validation_stage": "10"},
            {"id": "H2", "hypothesis": "次日留存不低于品类基准", "validation_stage": "10"},
        ],
    }


def _manifest(direction=None):
    return {
        "contract_version": "1",
        "stage": "03",
        "artifacts": [{"role": "direction_card", "path": "交付物_03.md"}],
        "risk_flags": {key: False for key in RISK_FLAG_KEYS},
        "direction": _direction() if direction is None else direction,
    }


def test_sheet_lists_audience_scope_and_how_to_validate():
    result = audit_stage("03", [json.dumps(_manifest(), ensure_ascii=False)])
    assert result["passed"], result["reasons"]
    sheet = describe_passed_stage("03", "产品方向决策", result)
    text = sheet["recommendation"] + sheet["evidence"]
    for piece in (
        "60 秒静音呼吸，打开就能用",
        "想在工位上立刻静下来的人",
        "60 秒呼吸",
        "结果保存",
        "长音频",
        "社群",
        "H1",
        "愿意为无广告付费",
        "H2",
        "次日留存不低于品类基准",
        "怎么验证：工序 10",
    ):
        assert piece in text
    assert sheet["recommendation"] in sheet["evidence"]
    assert "H1：愿意为无广告付费。怎么验证：工序 10。" in sheet["evidence"].splitlines()
    assert "H2：次日留存不低于品类基准。怎么验证：工序 10。" in sheet["evidence"].splitlines()


def test_missing_audience_or_validation_fails():
    missing_audience = _direction()
    missing_audience["target_audience"] = ""
    reasons = validate_manifest(_manifest(missing_audience))
    assert any("给谁做" in reason for reason in reasons)

    missing_validation = _direction()
    missing_validation["hypotheses"] = [
        {"id": "H1", "hypothesis": "愿意为无广告付费"},
        {"id": "H2", "hypothesis": "次日留存不低于品类基准", "validation_stage": "10"},
    ]
    reasons = validate_manifest(_manifest(missing_validation))
    assert any("缺少验证方式" in reason for reason in reasons)
