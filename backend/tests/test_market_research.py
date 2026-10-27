import pytest
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.app.services.market_research_engine import (
    calculate_tam_sam_som,
    detect_category,
    generate_comprehensive_market_report
)
from backend.app.services.domain_qa import generate_domain_qa_answer

def test_tam_sam_som_calculation():
    """Verify bottom-up TAM/SAM/SOM mathematical model."""
    cat = detect_category("WnPager", "WN-PAGER", "北美市场 (美国、加拿大)", "高审美锁屏景深壁纸")
    assert "wallpaper" in cat["category_name"].lower() or "美化" in cat["category_name"]

    res_na = calculate_tam_sam_som(cat, "北美市场")
    assert res_na["tam_usd"] > 1000000000 # > $1B
    assert res_na["sam_usd"] > 100000000  # > $100M
    assert res_na["som_base_users"] > 0
    assert res_na["som_base_revenue_usd"] > 0
    assert "conservative" in res_na["scenarios"]
    assert "base" in res_na["scenarios"]
    assert "optimistic" in res_na["scenarios"]

def test_market_research_report_generation():
    """Verify that comprehensive report synthesizes all 6 required institutional sections."""
    report = generate_comprehensive_market_report(
        product_name="WnPager",
        product_code="WN-PAGER",
        target_market="北美市场 (美国、加拿大)",
        strategic_intent="以极简美学工具切入北美壁纸美化市场",
        strategic_role="acquisition"
    )
    assert "# 《WnPager》市场研究与竞品深度洞察报告" in report
    assert "一、 TAM / SAM / SOM 市场空间测算模型" in report
    assert "二、 核心竞品 Top 5 横向对比矩阵" in report
    assert "Zedge" in report
    assert "Backdrops" in report
    assert "Vellum" in report
    assert "三、 用户画像与真实痛点挖掘 (ICP & Jobs-To-Be-Done)" in report
    assert "四、 差异化破局切入点与战略切口" in report
    assert "五、 平台生态趋势与合规风险排查" in report
    assert "六、 对下游工序的输入建议与行动清单" in report

def test_domain_qa_market_research_inquiries():
    """Verify market research questions yield structured, specialized responses."""
    ctx_meta = {
        "initiative_name": "北美工具类应用矩阵战役",
        "product_name": "WnPager",
        "product_code": "WN-PAGER",
        "target_market": "北美市场 (美国、加拿大)",
        "business_model_hypothesis": "免费图库引流 + $14.99/年订阅 + $29.99 买断"
    }

    # 1. TAM/SAM/SOM question
    q_tam = "本产品的 TAM/SAM/SOM 市场空间测算是怎么推演的？"
    ans_tam = generate_domain_qa_answer(q_tam, "市场研究", "", ctx_meta)
    assert "TAM / SAM / SOM 市场空间测算报告" in ans_tam
    assert "Blended ARPU" in ans_tam
    assert "基准情景" in ans_tam

    # 2. Competitors question
    q_comp = "请分析一下北美市场的主要竞品与差评槽点"
    ans_comp = generate_domain_qa_answer(q_comp, "市场研究", "", ctx_meta)
    assert "标杆竞品横向对比" in ans_comp
    assert "Zedge" in ans_comp
    assert "1-2 星核心差评" in ans_comp

    # 3. Personas question
    q_persona = "目标用户画像 (ICP) 和痛点有哪些？"
    ans_persona = generate_domain_qa_answer(q_persona, "市场研究", "", ctx_meta)
    assert "目标用户画像 (ICP)" in ans_persona
    assert "Jobs-To-Be-Done" in ans_persona

    # 4. Wedge question
    q_wedge = "面对大厂竞品，我们的差异化破局切入点 (Wedge) 是什么？"
    ans_wedge = generate_domain_qa_answer(q_wedge, "市场研究", "", ctx_meta)
    assert "Wedge" in ans_wedge
    assert "差异化破局切入点" in ans_wedge

@pytest.mark.asyncio
async def test_module_01_session_and_artifact_generation():
    """Verify end-to-end execution of Module 01 in ModuFlow session."""
    import uuid
    uid = uuid.uuid4().hex[:4].upper()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create initiative and product
        init_res = await client.post("/api/v1/initiatives", json={
            "name": f"北美工具类矩阵战役-{uid}",
            "owner": "Founder",
            "target_market": "北美市场 (美国、加拿大)",
            "strategic_intent": "以轻量美化工具形成高频低CAC流量入口"
        })
        assert init_res.status_code == 200
        init_id = init_res.json()["id"]

        prod_res = await client.post("/api/v1/products", json={
            "name": f"WnPager-{uid}",
            "code": f"WN-{uid}",
            "initiative_id": init_id,
            "auto_authorize": True
        })
        assert prod_res.status_code == 200
        prod_id = prod_res.json()["id"]

        run_res = await client.post("/api/v1/runs", json={
            "product_id": prod_id,
            "template_id": "full-product-launch",
            "name": "2026-Q1-Launch"
        })
        run_data = run_res.json()
        m01 = next(m for m in run_data["modules"] if m["module_code"] == "01")

        # Get session
        sess_res = await client.get(f"/api/v1/modules/{m01['id']}/session")
        assert sess_res.status_code == 200
        sess_id = sess_res.json()["id"]

        # 1. Ask a question about TAM/SAM/SOM
        q_res = await client.post(f"/api/v1/sessions/{sess_id}/messages", json={
            "sender": "Alice",
            "sender_role": "product_manager",
            "message_type": "question",
            "content": "请用自下而上模型测算本产品的 TAM/SAM/SOM 市场空间"
        })
        assert q_res.status_code == 200
        q_msgs = q_res.json()
        assert len(q_msgs) >= 2
        agent_reply = q_msgs[-1]
        assert agent_reply["message_type"] == "answer"
        assert "TAM / SAM / SOM" in agent_reply["content"]

        # 2. Send instruction to generate full deliverable
        inst_res = await client.post(f"/api/v1/sessions/{sess_id}/messages", json={
            "sender": "Alice",
            "sender_role": "product_manager",
            "message_type": "instruction",
            "content": "生成正式的市场研究与竞品分析报告交付物"
        })
        assert inst_res.status_code == 200
        inst_msgs = inst_res.json()
        agent_inst_reply = inst_msgs[-1]
        assert agent_inst_reply["message_type"] == "draft_artifact"
        assert agent_inst_reply["artifact_ref_id"] is not None

        # Verify artifact content
        art_res = await client.get(f"/api/v1/artifacts/{agent_inst_reply['artifact_ref_id']}")
        assert art_res.status_code == 200
        art_data = art_res.json()
        assert "WnPager" in art_data["content"]
        assert "TAM / SAM / SOM" in art_data["content"]
        assert "Zedge" in art_data["content"]
