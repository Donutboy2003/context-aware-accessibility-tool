"""
Shared pytest fixtures.

Forces the app to load with:
  - a temporary SQLite DB (so tests don't pollute /app/data/scholar.db)
  - LLM disabled (USE_LLM=0) so tests are deterministic and offline
  - the real /app/data/blog_words.txt (so blog seeding is exercised)

main.py reads these env vars at import time, so they MUST be set before
`import main` happens. We do that here, then yield a FastAPI TestClient.
"""
import os
import sys
import tempfile

import pytest


@pytest.fixture(scope="session")
def client():
    tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp_db.close()

    os.environ["DB_PATH"] = tmp_db.name
    os.environ["USE_LLM"] = "0"
    os.environ.pop("CEREBRAS_API_KEY", None)

    # Make sure the backend package root is importable
    backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)

    # Force a fresh import so the test DB / env are picked up
    for mod in ("main",):
        if mod in sys.modules:
            del sys.modules[mod]

    from fastapi.testclient import TestClient
    import main  # noqa: E402

    with TestClient(main.app) as c:
        yield c

    try:
        os.unlink(tmp_db.name)
    except OSError:
        pass
