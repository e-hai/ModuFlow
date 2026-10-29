from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.core.config import settings
from backend.app.core.database import engine, Base, AsyncSessionLocal
from backend.app.api.endpoints import api_router
from backend.app.services.workflow_engine import seed_templates_if_empty
from backend.app.services.agent_roles import seed_agent_roles_if_empty, migrate_db_for_roles

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Safe SQLite column migration and role seeding
    async with AsyncSessionLocal() as db:
        await migrate_db_for_roles(db)
        await seed_agent_roles_if_empty(db)
        await seed_templates_if_empty(db)
        
        from backend.app.adapters.cli_adapter import apply_saved_cli_settings
        await apply_saved_cli_settings(db)
        
    yield
    # Shutdown
    await engine.dispose()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/health")
async def health_check():
    return {"status": "ok", "app": settings.PROJECT_NAME}
