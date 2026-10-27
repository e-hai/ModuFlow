import os
import yaml
from pathlib import Path
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from backend.app.core.database import Base, get_db
from backend.app.main import app
from backend.app.core.config import settings
from scripts.migrate_legacy_project_auth import generate_default_authorization_dict
from backend.app.services.authorization_engine import get_product_authorization_path

TEST_DB_PATH = "./data/test_moduflow.db"
TEST_DATABASE_URL = f"sqlite+aiosqlite:///{TEST_DB_PATH}"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False}
)

TestingSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

async def override_get_db():
    async with TestingSessionLocal() as session:
        yield session

# Override FastAPI database dependency for all test runs
app.dependency_overrides[get_db] = override_get_db


def ensure_test_product_authorization(initiative_id: str, product_code: str, budget: float = 5000.0) -> Path:
    auth_path = get_product_authorization_path(initiative_id, product_code)
    auth_path.parent.mkdir(parents=True, exist_ok=True)
    data = generate_default_authorization_dict(product_code, product_code, budget)
    auth_path.write_text(yaml.dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return auth_path
