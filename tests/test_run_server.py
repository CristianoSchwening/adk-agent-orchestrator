from __future__ import annotations

import runpy
import sys


def test_run_server_loads_repository_env_before_starting_uvicorn(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text("GOOGLE_API_KEY=test-key-from-dotenv\n", encoding="utf-8")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setattr("pathlib.Path.resolve", lambda self: tmp_path / "run_server.py")

    class UvicornStub:
        @staticmethod
        def run(*args, **kwargs):
            raise AssertionError("uvicorn must not start when run_server is imported")

    monkeypatch.setitem(sys.modules, "uvicorn", UvicornStub())
    namespace = runpy.run_path("run_server.py", run_name="run_server_test")

    assert namespace["REPOSITORY_ROOT"] == tmp_path
    assert namespace["load_dotenv"] is not None
    assert __import__("os").environ["GOOGLE_API_KEY"] == "test-key-from-dotenv"
