"""
Integration tests for the FastAPI endpoints.

LLM is forced OFF (USE_LLM=0 set in conftest.py) so suggestions come purely
from the trie + scoring path. This keeps tests deterministic and offline.
"""
import pytest


# ── /health ───────────────────────────────────────────────────────────────────


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


# ── /suggest basic behavior ───────────────────────────────────────────────────


def test_suggest_empty_prefix_returns_empty(client):
    r = client.post("/suggest", json={"prefix": "", "prev_words": [], "mic_transcript": ""})
    assert r.status_code == 200
    body = r.json()
    assert body["suggestions"] == []
    assert body["source"] == "trie"


def test_suggest_source_is_trie_when_llm_disabled(client):
    r = client.post("/suggest", json={"prefix": "khut"})
    assert r.status_code == 200
    assert r.json()["source"] == "trie"


def test_suggest_returns_at_most_8_suggestions(client):
    r = client.post("/suggest", json={"prefix": "a"})
    assert r.status_code == 200
    assert len(r.json()["suggestions"]) <= 8


def test_suggest_unknown_prefix_returns_empty(client):
    r = client.post("/suggest", json={"prefix": "zzqxv"})
    assert r.status_code == 200
    assert r.json()["suggestions"] == []


# ── /suggest with real seeded vocabulary ──────────────────────────────────────


@pytest.mark.parametrize(
    "prefix,expected_word",
    [
        # From backend/word_list.py
        ("khut", "khutbah"),
        ("sal",  "salah"),
        ("hadi", "hadith"),
        ("sun",  "sunnah"),
        ("fiq",  "fiqh"),
        # From data/blog_words.txt
        ("tazk", "tazkiyah"),
        ("muja", "mujahada"),
        ("isti", "istiqamah"),
        ("bara", "barakah"),
        ("qal",  "qalb"),
        ("naf",  "nafs"),
    ],
)
def test_suggest_finds_seeded_word(client, prefix, expected_word):
    r = client.post("/suggest", json={"prefix": prefix})
    assert r.status_code == 200
    suggestions = [s.lower() for s in r.json()["suggestions"]]
    assert expected_word in suggestions, f"{expected_word!r} missing from {suggestions}"


def test_suggest_is_case_insensitive(client):
    lower = client.post("/suggest", json={"prefix": "khut"}).json()["suggestions"]
    upper = client.post("/suggest", json={"prefix": "KHUT"}).json()["suggestions"]
    assert lower == upper


# ── Mic-transcript context boost ──────────────────────────────────────────────


def test_mic_transcript_boosts_relevant_word(client):
    """A word mentioned in the mic transcript should rank higher than it would otherwise."""
    # Without context
    base = client.post("/suggest", json={"prefix": "ta"}).json()["suggestions"]
    # With "tazkiyah" in the transcript — it should rank at or near the top
    boosted = client.post("/suggest", json={
        "prefix": "ta",
        "mic_transcript": "today we discuss tazkiyah and its importance",
    }).json()["suggestions"]

    assert "tazkiyah" in [w.lower() for w in boosted]
    # tazkiyah should rank higher (smaller index) when mic-boosted
    if "tazkiyah" in [w.lower() for w in base]:
        assert boosted.index("tazkiyah") <= base.index("tazkiyah")
    else:
        # If it wasn't in the unboosted top-8 at all, it must now be — that's a stronger pass
        assert "tazkiyah" in [w.lower() for w in boosted]


# ── /learn ────────────────────────────────────────────────────────────────────


def test_learn_persists_word_and_boosts_future_suggestions(client):
    # Learn a brand-new word that isn't seeded anywhere
    word = "munajaat"
    r = client.post("/learn", json={"selected_word": word, "prev_word": "nightly"})
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

    # It should now appear when we ask for its prefix
    r = client.post("/suggest", json={"prefix": "muna"})
    assert r.status_code == 200
    assert word in [s.lower() for s in r.json()["suggestions"]]


def test_learn_rejects_empty_word(client):
    r = client.post("/learn", json={"selected_word": "   "})
    assert r.status_code == 400


def test_learn_repeated_increases_ranking(client):
    """Calling /learn multiple times on the same word should boost it above competitors."""
    # Pick a fresh prefix space
    client.post("/learn", json={"selected_word": "zaynab"})
    client.post("/learn", json={"selected_word": "zayd"})
    # Boost zayd many times
    for _ in range(20):
        client.post("/learn", json={"selected_word": "zayd"})
    suggestions = client.post("/suggest", json={"prefix": "zay"}).json()["suggestions"]
    assert "zayd" in suggestions and "zaynab" in suggestions
    assert suggestions.index("zayd") < suggestions.index("zaynab")
