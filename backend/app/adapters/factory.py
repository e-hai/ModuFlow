from typing import Optional
from backend.app.core.config import settings
from backend.app.adapters.base import BaseAgentAdapter
from backend.app.adapters.cli_adapter import CliSubprocessAdapter
from backend.app.adapters.simulator_adapter import SimulatorAdapter

def get_agent_adapter(adapter_type: Optional[str] = None) -> BaseAgentAdapter:
    """
    Factory function to obtain the configured Agent Adapter instance.
    Supports 'cli', 'simulator', and custom adapter extensions.
    """
    selected = adapter_type or settings.AGENT_ADAPTER_TYPE
    if selected == "simulator" or settings.AGENT_CLI_COMMAND == "simulator":
        return SimulatorAdapter()
    elif selected == "cli":
        return CliSubprocessAdapter()
    else:
        return CliSubprocessAdapter()
