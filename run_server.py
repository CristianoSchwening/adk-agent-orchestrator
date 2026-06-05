"""Entry point to run the ADK Orchestrator webapp server."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "orchestrator.server:app",
        host="0.0.0.0",
        port=5000,
        reload=False,
        log_level="info",
    )
