"""工序 02 确认单用大白话列出五个输入、乘出来的结果和价格。"""

import json

from backend.app.services.deliverable_audit import audit_stage, audit_unit_economics
from backend.app.services.delivery_contract import RISK_FLAG_KEYS
from backend.app.services.gate_copy import describe_passed_stage


def _manifest():
    organic, cpi, ad, conversion, arppu = 0.4, 2.0, 1.5, 0.1, 30.0
    cac = round((1.0 - organic) * cpi, 3)
    ltv = round(ad + conversion * arppu, 3)
    ratio = round(ltv / cac, 2)
    return {
        "contract_version": "1",
        "stage": "02",
        "artifacts": [{"role": "report", "path": "交付物_02.md"}],
        "risk_flags": {key: False for key in RISK_FLAG_KEYS},
        "unit_economics": {
            "organic_share": organic,
            "paid_cpi_usd": cpi,
            "ad_arpu_usd": ad,
            "iap_conversion_rate": conversion,
            "iap_net_arppu_usd": arppu,
            "blended_cac_usd": cac,
            "ltv_180d_usd": ltv,
            "ltv_cac_ratio": ratio,
            "pricing_tiers": [
                {"tier_id": "month", "name": "月卡", "price_usd": 9.99},
                {"tier_id": "year", "name": "年卡", "price_usd": 49.99},
            ],
        },
    }


def test_sheet_lists_inputs_product_and_prices():
    result = audit_stage("02", [json.dumps(_manifest(), ensure_ascii=False)])
    assert result["passed"], result["reasons"]
    assert result["blended_cac_usd"] == 1.2
    assert result["ltv_180d_usd"] == 4.5
    assert result["ltv_cac_ratio"] == 3.75
    sheet = describe_passed_stage("02", "商业模式", result)
    text = sheet["recommendation"] + sheet["evidence"]
    for piece in ("40%", "2.00 美元", "1.50 美元", "10%", "30.00 美元", "1.20 美元", "4.50 美元", "3.75", "月卡", "9.99", "年卡", "49.99"):
        assert piece in text
    assert "获客成本 =（1 − 自然来的占比）× 单个安装成本。" in sheet["evidence"]
    assert "180 天客户价值 = 广告收入 + 付钱占比 × 净付金额。" in sheet["evidence"]
    assert sheet["recommendation"] in sheet["evidence"]


def test_ratio_below_three_still_fails():
    result = audit_unit_economics([
        '{"organic_share": 0.0, "paid_cpi_usd": 2.0, "ad_arpu_usd": 0.5, '
        '"iap_conversion_rate": 0.01, "iap_net_arppu_usd": 10}'
    ])
    assert result["passed"] is False
    assert any("低于 3.0" in reason for reason in result["reasons"])
