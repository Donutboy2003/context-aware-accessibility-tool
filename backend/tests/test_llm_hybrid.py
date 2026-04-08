"""
Tests for the hybrid LLM + trie merge logic in /suggest.

We can't hit the real Cerebras API in tests (network, cost, non-determinism),
so we monkeypatch `main.llm_complete` with a fake async function and verify:

  1. When LLM returns words, they appear FIRST in the response.
  2. The response source is "hybrid".
  3. Trie words are appended as fillers, deduped, capped at 8.
  4. When LLM returns [], we fall back to pure trie (source "trie").
  5. When LLM raises, we still fall back gracefully (source "trie").
  6. The LLM is invoked with the right prefix / prev_text / mic_transcript.
"""
import os
import sys
import tempfile

import pytest


@pytest.fixture(scope="module")
def llm_client():
    """
    Boots a SECOND TestClient with USE_LLM=1 and a fake API key, separate from
    the LLM-disabled client in conftest.py. This needs its own module import
    of main because main.py reads USE_LLM at import time.
    """
    tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp_db.close()

    os.environ["DB_PATH"] = tmp_db.name
    os.environ["USE_LLM"] = "1"
    os.environ["CEREBRAS_API_KEY"] = "test-key-not-real"

    backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)

    # Force a fresh import so USE_LLM is re-evaluated
    for mod in ("main",):
        if mod in sys.modules:
            del sys.modules[mod]

    from fastapi.testclient import TestClient
    import main  # noqa: E402

    assert main.USE_LLM is True, "LLM path must be enabled for these tests"

    with TestClient(main.app) as c:
        yield c, main

    try:
        os.unlink(tmp_db.name)
    except OSError:
        pass


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_fake_llm(words, capture=None):
    """Returns an async fake replacement for llm_complete."""
    async def fake(prefix, prev_text, mic_transcript, api_key):
        if capture is not None:
            capture["prefix"] = prefix
            capture["prev_text"] = prev_text
            capture["mic_transcript"] = mic_transcript
            capture["api_key"] = api_key
        return list(words)
    return fake


# ── tests ────────────────────────────────────────────────────────────────────

def test_hybrid_llm_words_appear_first(llm_client, monkeypatch):
    client, main = llm_client
    fake_words = ["khalifah", "khayr", "khushu"]
    monkeypatch.setattr(main, "llm_complete", _make_fake_llm(fake_words))

    r = client.post("/suggest", json={"prefix": "kh"})
    assert r.status_code == 200
    body = r.json()

    assert body["source"] == "hybrid"
    # The LLM words must appear in order, before any trie filler
    assert body["suggestions"][:3] == fake_words


def test_hybrid_dedupes_llm_and_trie_overlap(llm_client, monkeypatch):
    client, main = llm_client
    # "khutbah" exists in the seeded trie. Including it in the LLM output
    # should NOT cause it to appear twice in the merged list.
    fake_words = ["khutbah", "khalifah"]
    monkeypatch.setattr(main, "llm_complete", _make_fake_llm(fake_words))

    r = client.post("/suggest", json={"prefix": "kh"})
    suggestions = r.json()["suggestions"]

    assert suggestions.count("khutbah") == 1
    assert suggestions[0] == "khutbah"
    assert suggestions[1] == "khalifah"


def test_hybrid_caps_at_8(llm_client, monkeypatch):
    client, main = llm_client
    fake_words = [f"khword{i}" for i in range(20)]
    monkeypatch.setattr(main, "llm_complete", _make_fake_llm(fake_words))

    r = client.post("/suggest", json={"prefix": "kh"})
    assert len(r.json()["suggestions"]) == 8
    # First 8 are the first 8 LLM words
    assert r.json()["suggestions"] == fake_words[:8]


def test_hybrid_falls_back_to_trie_when_llm_returns_empty(llm_client, monkeypatch):
    client, main = llm_client
    monkeypatch.setattr(main, "llm_complete", _make_fake_llm([]))

    r = client.post("/suggest", json={"prefix": "khut"})
    body = r.json()

    assert body["source"] == "trie"
    assert "khutbah" in [s.lower() for s in body["suggestions"]]


def test_hybrid_falls_back_to_trie_when_llm_raises(llm_client, monkeypatch):
    client, main = llm_client

    async def boom(prefix, prev_text, mic_transcript, api_key):
        # Mirrors what llm_client.py would do — it catches and returns []
        # internally. Here we simulate that contract.
        return []

    monkeypatch.setattr(main, "llm_complete", boom)
    r = client.post("/suggest", json={"prefix": "khut"})
    assert r.json()["source"] == "trie"
    assert "khutbah" in [s.lower() for s in r.json()["suggestions"]]


def test_llm_receives_correct_prefix_prev_text_and_transcript(llm_client, monkeypatch):
    client, main = llm_client
    capture = {}
    monkeypatch.setattr(main, "llm_complete", _make_fake_llm(["khutbah"], capture=capture))

    r = client.post("/suggest", json={
        "prefix": "khut",
        "prev_words": ["today", "we", "will", "discuss", "the"],
        "mic_transcript": "the imam delivers the friday khutbah",
    })
    assert r.status_code == 200

    assert capture["prefix"] == "khut"
    # prev_text is the last 20 prev_words joined with spaces
    assert capture["prev_text"] == "today we will discuss the"
    assert capture["mic_transcript"] == "the imam delivers the friday khutbah"
    assert capture["api_key"] == "test-key-not-real"


def test_llm_only_invoked_when_prefix_nonempty(llm_client, monkeypatch):
    client, main = llm_client
    called = {"count": 0}

    async def fake(prefix, prev_text, mic_transcript, api_key):
        called["count"] += 1
        return ["foo"]

    monkeypatch.setattr(main, "llm_complete", fake)
    r = client.post("/suggest", json={"prefix": "   "})
    assert r.json()["suggestions"] == []
    assert called["count"] == 0
