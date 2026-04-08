"""
Unit tests for the Trie data structure.

These tests use real vocabulary from word_list.py and blog_words.txt so they
double as a sanity check that our seeded data behaves as expected.
"""
import pytest

from trie import Trie


# ── Construction & basic insert / lookup ──────────────────────────────────────


def test_insert_and_get_frequency():
    t = Trie()
    t.insert("khutbah", 20)
    assert t.get_frequency("khutbah") == 20
    # case-insensitive
    assert t.get_frequency("KHUTBAH") == 20
    assert t.get_frequency("Khutbah") == 20


def test_get_frequency_unknown_word_returns_zero():
    t = Trie()
    t.insert("salah", 10)
    assert t.get_frequency("nonexistent") == 0
    # Prefix of a known word but not itself a stored word
    assert t.get_frequency("sal") == 0


def test_insert_duplicate_keeps_higher_frequency():
    t = Trie()
    t.insert("tawbah", 5)
    t.insert("tawbah", 25)
    assert t.get_frequency("tawbah") == 25
    # Re-inserting with a lower freq must not lower it
    t.insert("tawbah", 1)
    assert t.get_frequency("tawbah") == 25


def test_boost_frequency_adds_to_existing():
    t = Trie()
    t.insert("qalb", 10)
    t.boost_frequency("qalb", 5)
    assert t.get_frequency("qalb") == 15


def test_boost_frequency_no_op_for_unknown_word():
    t = Trie()
    t.boost_frequency("ghost", 99)
    assert t.get_frequency("ghost") == 0


# ── Prefix search ─────────────────────────────────────────────────────────────


def test_search_prefix_returns_all_matches_sorted_by_frequency():
    t = Trie()
    t.insert("tawbah", 25)
    t.insert("tawadu", 10)
    t.insert("tawfiq", 15)
    t.insert("salah", 30)  # unrelated, should not appear

    results = t.search_prefix("taw", max_results=10)
    words = [w for w, _ in results]

    assert "salah" not in words
    assert set(words) == {"tawbah", "tawadu", "tawfiq"}
    # sorted by frequency descending
    freqs = [f for _, f in results]
    assert freqs == sorted(freqs, reverse=True)
    assert words[0] == "tawbah"


def test_search_prefix_no_matches_returns_empty():
    t = Trie()
    t.insert("salah", 10)
    assert t.search_prefix("zzz") == []


def test_search_prefix_exact_word_is_returned():
    t = Trie()
    t.insert("noor", 10)
    results = t.search_prefix("noor")
    assert ("noor", 10) in results


def test_search_prefix_respects_max_results():
    t = Trie()
    for i, w in enumerate(["aaa", "aab", "aac", "aad", "aae"]):
        t.insert(w, 10 - i)
    results = t.search_prefix("a", max_results=3)
    assert len(results) == 3
    # Should keep the top-3 by frequency
    assert [w for w, _ in results] == ["aaa", "aab", "aac"]


# ── Real seeded vocabulary (blog_words.txt + word_list.py) ────────────────────


@pytest.fixture(scope="module")
def seeded_trie():
    """Mirrors the seeding logic in main.py — built-ins + blog file."""
    import os
    from word_list import ISLAMIC_WORDS

    t = Trie()
    for word, freq in ISLAMIC_WORDS:
        t.insert(word, freq)

    # blog_words.txt is mounted into the container at /app/data/
    candidate_paths = [
        os.getenv("BLOG_WORDS_PATH", "/app/data/blog_words.txt"),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "blog_words.txt")),
    ]
    for p in candidate_paths:
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                for line in f:
                    word = line.strip()
                    if word and not word.startswith("#"):
                        t.insert(word, 10)
            break
    return t


@pytest.mark.parametrize(
    "prefix,expected_word",
    [
        ("khut", "khutbah"),     # word_list.py
        ("sal",  "salah"),       # word_list.py
        ("quran", "quran"),      # word_list.py (stored lowercase via insert)
        ("hadi", "hadith"),      # word_list.py
        ("sun",  "sunnah"),      # word_list.py
        ("fiq",  "fiqh"),        # word_list.py
        ("tazk", "tazkiyah"),    # blog_words.txt
        ("muja", "mujahada"),    # blog_words.txt
        ("muha", "muhasabah"),   # blog_words.txt
        ("isti", "istiqamah"),   # blog_words.txt
        ("bara", "barakah"),     # blog_words.txt
        ("base", "baseerah"),    # blog_words.txt
        ("qal",  "qalb"),        # blog_words.txt
        ("naf",  "nafs"),        # blog_words.txt
    ],
)
def test_seeded_vocabulary_returns_expected_completion(seeded_trie, prefix, expected_word):
    results = seeded_trie.search_prefix(prefix, max_results=20)
    words = [w.lower() for w, _ in results]
    assert expected_word in words, f"{expected_word!r} not in suggestions for prefix {prefix!r}: {words}"
