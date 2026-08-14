"""Entry point to run the ADK Orchestrator webapp server."""

import sys
from pathlib import Path

import uvicorn
from dotenv import load_dotenv

REPOSITORY_ROOT = Path(__file__).resolve().parent
load_dotenv(REPOSITORY_ROOT / ".env")

sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

if __name__ == "__main__":
    uvicorn.run(
        "orchestrator.server:app",
        host="0.0.0.0",
        port=5000,
        reload=False,
        log_level="info",
    )
