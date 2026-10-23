#!/usr/bin/env python3
"""
ModuFlow Database Seeding Script.
Initializes templates, 8 core agent roles, and ensures schema columns exist without committing personal data.
"""
import asyncio
from backend.app.core.database import AsyncSessionLocal, engine, Base
from backend.app.services.workflow_engine import seed_templates_if_empty
from backend.app.services.agent_roles import seed_agent_roles_if_empty, migrate_db_for_roles
from backend.app.models.entities import AgentSettingsModel
from sqlalchemy import select

async def main():
    print("🌱 [ModuFlow] Initializing database schema...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        print("🔧 [ModuFlow] Running column migrations...")
        await migrate_db_for_roles(db)

        print("🤖 [ModuFlow] Seeding 8 core Agent Roles...")
        await seed_agent_roles_if_empty(db)

        print("📋 [ModuFlow] Seeding standard workflow templates...")
        await seed_templates_if_empty(db)

        # Seed default agent settings if missing
        stmt = select(AgentSettingsModel).where(AgentSettingsModel.id == "default")
        res = await db.execute(stmt)
        if not res.scalar_one_or_none():
            print("⚙️ [ModuFlow] Seeding default agent settings (agy CLI)...")
            default_settings = AgentSettingsModel(
                id="default",
                adapter_type="cli",
                cli_command="agy",
                timeout=90
            )
            db.add(default_settings)
            await db.commit()

    print("✅ [ModuFlow] Seeding complete! Database is clean and ready.")

if __name__ == "__main__":
    asyncio.run(main())
