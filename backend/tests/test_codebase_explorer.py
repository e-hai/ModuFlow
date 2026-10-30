import pytest
from pathlib import Path
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.app.core.database import AsyncSessionLocal
from backend.app.models.entities import ModuleInstance, WorkflowRun, Product, StrategicInitiative
from backend.app.services.codebase_explorer import (
    detect_file_language,
    get_codebase_summary_and_tree,
    read_codebase_file,
    open_codebase_in_local_ide
)


def test_detect_file_language():
    assert detect_file_language("Session.kt") == "kotlin"
    assert detect_file_language("build.gradle.kts") == "gradle"
    assert detect_file_language("AppDelegate.swift") == "swift"
    assert detect_file_language("gradlew") == "bash"
    assert detect_file_language("config.json") == "json"
    assert detect_file_language("unknown.xyz") == "plaintext"


def test_get_codebase_summary_and_tree(tmp_path):
    # Setup mock codebase
    shared = tmp_path / "shared" / "src" / "commonMain"
    shared.mkdir(parents=True)
    (shared / "App.kt").write_text("package com.test\nclass App\n", encoding="utf-8")
    (tmp_path / "build.gradle.kts").write_text("plugins { kotlin(\"multiplatform\") }\n", encoding="utf-8")
    
    # Ignored directory
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    (build_dir / "temp.txt").write_text("temp", encoding="utf-8")

    result = get_codebase_summary_and_tree(tmp_path)
    assert result["exists"] is True
    assert result["total_files"] == 2
    assert result["total_lines"] >= 3
    
    names = [node["name"] for node in result["tree"]]
    assert "shared" in names
    assert "build.gradle.kts" in names
    assert "build" not in names  # build directory ignored


def test_read_codebase_file(tmp_path):
    file_p = tmp_path / "Main.kt"
    file_p.write_text("fun main() = println(\"hi\")\n", encoding="utf-8")

    res = read_codebase_file(tmp_path, "Main.kt")
    assert res["name"] == "Main.kt"
    assert res["language"] == "kotlin"
    assert "fun main()" in res["content"]

    # Traversal attack protection
    with pytest.raises(PermissionError):
        read_codebase_file(tmp_path, "../outside.txt")


@pytest.mark.asyncio
async def test_codebase_endpoints(monkeypatch, tmp_path):
    # Mock resolve_module_codebase_dir
    shared = tmp_path / "shared"
    shared.mkdir()
    (shared / "Model.kt").write_text("data class Model(val id: String)", encoding="utf-8")

    async def _mock_resolve(db, module_id):
        class MockMod:
            id = module_id
            order_index = 7
            module_code = "07"
            name = "开发实现"
        return MockMod(), tmp_path, tmp_path

    monkeypatch.setattr("backend.app.services.codebase_explorer.resolve_module_codebase_dir", _mock_resolve)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Test tree
        res = await ac.get("/api/v1/modules/mod-test-07/codebase-tree")
        assert res.status_code == 200
        data = res.json()
        assert data["exists"] is True
        assert data["total_files"] == 1
        assert data["tree"][0]["name"] == "shared"

        # Test file content
        file_res = await ac.get("/api/v1/modules/mod-test-07/codebase-file?path=shared/Model.kt")
        assert file_res.status_code == 200
        file_data = file_res.json()
        assert file_data["language"] == "kotlin"
        assert "data class Model" in file_data["content"]
