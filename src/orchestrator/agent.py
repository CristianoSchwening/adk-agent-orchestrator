"""ADK discovery module.

The ADK CLI and web tooling expect an ``agent.py`` module containing a
``root_agent`` object. This file intentionally mirrors that convention.
"""

from orchestrator.agents import create_root_agent
from orchestrator.config import OrchestratorSettings

root_agent = create_root_agent(OrchestratorSettings.from_env())
