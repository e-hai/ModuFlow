from enum import Enum
from typing import AsyncIterator, Optional, Dict, Any
from pathlib import Path
from pydantic import BaseModel
from abc import ABC, abstractmethod

class AgentEventType(str, Enum):
    LOG = "log"
    THINKING = "thinking"
    ARTIFACT_DRAFT = "artifact_draft"
    ARTIFACT_REVISED = "artifact_revised"
    ISSUE_FOUND = "issue_found"
    DONE = "done"
    ERROR = "error"

class AgentStreamEvent(BaseModel):
    event_type: AgentEventType
    content: str
    metadata: Optional[Dict[str, Any]] = None

class BaseAgentAdapter(ABC):
    """
    Abstract Base Class for all ModuFlow Agent Adapters.
    Decouples core product R&D workflow from underlying AI agent execution runtimes:
    - CLI Subprocess (Claude Code, Antigravity agy, Aider, custom CLI)
    - Direct LLM API
    - Local Rule-based Simulator (for offline/testing)
    """

    @abstractmethod
    async def execute_task(
        self,
        task_id: str,
        workspace_dir: Path,
        system_context: str,
        user_instruction: str,
        message_type: str = "instruction",
        metadata: Optional[Dict[str, Any]] = None
    ) -> AsyncIterator[AgentStreamEvent]:
        """
        Executes a task inside the isolated physical workspace directory.
        Yields real-time structured events (logs, thoughts, artifacts, issues).
        """
        pass

    @abstractmethod
    async def cancel_task(self, task_id: str) -> bool:
        """Cancels/kills an active task or subprocess."""
        pass
