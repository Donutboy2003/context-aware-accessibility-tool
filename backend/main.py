import math
import os
import tempfile
from typing import Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import Database
from transcriber import transcribe_audio
from trie import Trie
from word_list import ISLAMIC_WORDS

# ── App setup ──────────────────────────────────────────────────────────────────

app = FastAPI(title="Islamic Scholar Writing Assistant", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Initialise trie + DB ───────────────────────────────────────────────────────

DB_PATH = os.getenv("DB_PATH", "/app/data/scholar.db")
BLOG_WORDS_PATH = os.getenv("BLOG_WORDS_PATH", "/app/data/blog_words.txt")

db = Database(DB_PATH)
trie = Trie()

# 1. Seed trie from built-in Islamic word list
for word, freq in ISLAMIC_WORDS:
    trie.insert(word, freq)

# 2. Seed from user's blog word file (if it exists)
if os.path.exists(BLOG_WORDS_PATH):
    with open(BLOG_WORDS_PATH, encoding="utf-8") as f:
        for line in f:
            word = line.strip()
            if word and not word.startswith("#"):
                # Blog words get a solid base frequency of 10
                trie.insert(word, 10)
    print(f"[Startup] Blog words loaded from {BLOG_WORDS_PATH}")

# 3. Overlay with learned frequencies from SQLite (higher priority)
for word, freq in db.get_all_words():
    trie.insert(word, freq)
    trie.boost_frequency(word, freq)

print(f"[Startup] Trie ready. DB: {DB_PATH}")


# ── Request / Response models ──────────────────────────────────────────────────

class SuggestRequest(BaseModel):
    prefix: str
    prev_words: list[str] = []
    mic_transcript: str = ""

class SuggestResponse(BaseModel):
    suggestions: list[str]

class LearnRequest(BaseModel):
    selected_word: str
    prev_word: Optional[str] = None

class LearnResponse(BaseModel):
    status: str


# ── Scoring ────────────────────────────────────────────────────────────────────

def score_candidates(
    candidates: list[tuple[str, int]],
    prefix: str,
    prev_word: Optional[str],
    mic_words: set[str],
) -> list[tuple[str, float]]:
    """
    Multi-factor scoring:
    1. Trie frequency (log-scaled) — base learned preference
    2. Mic transcript overlap — boosts contextually relevant words
    3. Bigram probability — boosts words that naturally follow prev_word
    4. Prefix coverage — slightly prefer shorter completions for same prefix
    """
    scored: list[tuple[str, float]] = []

    for word, freq in candidates:
        word_lower = word.lower()

        # 1. Base frequency (log-scaled so very common words don't dominate)
        base = math.log(freq + 1) * 10

        # 2. Mic context boost (strong signal)
        mic_boost = 25.0 if word_lower in mic_words else 0.0
        # Partial match — word is a prefix of a mic word or vice versa
        for mw in mic_words:
            if mw.startswith(word_lower) or word_lower.startswith(mw):
                mic_boost = max(mic_boost, 12.0)

        # 3. Bigram boost (strong signal)
        bigram_boost = 0.0
        if prev_word:
            bigram_freq = db.get_bigram_freq(prev_word, word_lower)
            bigram_boost = math.log(bigram_freq + 1) * 20

        # 4. Prefix coverage ratio (minor tie-breaker)
        coverage = len(prefix) / max(len(word), 1)
        coverage_score = coverage * 3

        total = base + mic_boost + bigram_boost + coverage_score
        scored.append((word, total))

    return scored


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/suggest", response_model=SuggestResponse)
def suggest(req: SuggestRequest):
    prefix = req.prefix.strip()
    if not prefix:
        return SuggestResponse(suggestions=[])

    # Get trie candidates (returns up to 30 prefix matches)
    candidates = trie.search_prefix(prefix, max_results=30)
    if not candidates:
        return SuggestResponse(suggestions=[])

    # Build mic context word set
    mic_words = {w.lower() for w in req.mic_transcript.split() if len(w) > 2}

    prev_word = req.prev_words[-1].lower() if req.prev_words else None

    # Score and rank
    scored = score_candidates(candidates, prefix, prev_word, mic_words)
    scored.sort(key=lambda x: -x[1])

    top = [word for word, _ in scored[:8]]
    return SuggestResponse(suggestions=top)


@app.post("/learn", response_model=LearnResponse)
def learn(req: LearnRequest):
    word = req.selected_word.strip().lower()
    if not word:
        raise HTTPException(status_code=400, detail="Empty word")

    # Persist to DB
    db.increment_word(word, amount=3)
    if req.prev_word:
        db.increment_bigram(req.prev_word.lower(), word, amount=1)

    # Update live trie (so effect is immediate without restart)
    trie.insert(word, 3)
    trie.boost_frequency(word, 3)

    return LearnResponse(status="ok")


@app.post("/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    content = await audio.read()
    if len(content) < 1000:
        # Too small to be real audio — likely silence/empty chunk
        return {"transcript": ""}

    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        # Run blocking Whisper in thread pool — keeps FastAPI responsive
        text = await run_in_threadpool(transcribe_audio, tmp_path)
        return {"transcript": text}
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
