from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "ModuFlow"
    API_V1_STR: str = "/api/v1"
    
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    SNAPSHOT_DIR: Path = DATA_DIR / "snapshots"
    WORKSPACE_DIR: Path = DATA_DIR / "workspaces"
    
    DATABASE_URL: str = f"sqlite+aiosqlite:///{DATA_DIR}/moduflow.db"
    
    # Agent Adapter Configuration
    AGENT_ADAPTER_TYPE: str = "cli"        # "cli" | "api"
    AGENT_CLI_COMMAND: str = "agy"         # Default CLI tool: e.g. "agy", "claude", or custom script
    AGENT_CLI_MODEL: str = ""             # Empty keeps the CLI's own selected model
    AGENT_CLI_TIMEOUT: int = 300          # Max execution seconds for a single CLI invocation (5 minutes for LLM reasoning & tools)

    # Global kill switch for automatic orchestration triggers; per-run control lives on WorkflowRun.auto_advance
    ORCHESTRATOR_ENABLED: bool = True
    RUNNER_POLL_SECONDS: float = 1.0      # Idle poll interval of the out-of-process stage runner
    RUNNER_STALE_SECONDS: int = 120       # No heartbeat for this long means the runner died; the job is requeued
    COLLAB_REVIEW_MODE: str = "full"      # "full": cross-checks + collaborator Agent reviews; "deterministic"; "off"
    AGENT_FS_SANDBOX: str = "auto"        # "auto": macOS sandbox-exec when available; "off": integrity check only
    
    model_config = SettingsConfigDict(case_sensitive=True)

settings = Settings()
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
settings.SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
settings.WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
