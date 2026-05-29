"""Small compatibility helpers around optional ADK imports.

The project declares ``google-adk`` as a runtime dependency. Tests that only
validate scaffolding can run without importing ADK, while actual execution uses
lazy imports to instantiate official ADK classes.
"""

from __future__ import annotations

from importlib import import_module, util
from typing import Any


def is_adk_installed() -> bool:
    """Return whether the Google ADK package is importable in this environment."""

    return util.find_spec("google") is not None and util.find_spec("google.adk") is not None


def load_symbol(module_name: str, symbol_name: str) -> Any:
    """Load an ADK symbol lazily.

    Lazy loading keeps module import side effects small and lets unit tests
    exercise configuration/policy code even when the ADK wheel is not installed
    in the current interpreter.
    """

    module = import_module(module_name)
    return getattr(module, symbol_name)
