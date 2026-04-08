# Islamic Scholar Writing Assistant

A local AI-powered writing tool for a Muslim scholar — mic-aware predictive text
suggestions with self-learning, tuned for Islamic scholarly vocabulary.

**Runs entirely on your Surface. No cloud. No subscriptions. No data leaves your device.**

---

## What It Does

| Feature | How |
|---|---|
| Predictive suggestions | Trie + bigram scoring on typed prefix |
| Mic context | Whisper (local) transcribes background speech every 5 s |
| Suggestion boost | Words heard in the room score higher |
| Self-learning | Every accepted suggestion raises that word's rank |
| Bigram learning | Tracks which words follow which, so "hadith → Bukhari" gets learned |
| Blog word list | `data/blog_words.txt` — seed from your own writing |
| Keyboard access | Tab = accept first · 1–6 = pick specific · ←/→ = navigate |

---

## Prerequisites

Install **Docker Desktop** on your Surface:
https://docs.docker.com/desktop/install/windows-install/

That is the only thing you need. Docker Desktop installs everything else.

---

## Quick Start

```bash
# 1. Open a terminal (PowerShell or Windows Terminal) in this folder
cd islamic-assist

# 2. Build and start (first build takes ~5-10 min — downloads Whisper model)
docker compose up --build

# 3. Open your browser
http://localhost:3000
```

To stop:
```bash
docker compose down
```

To start again later (no rebuild needed):
```bash
docker compose up
```

---

## First-Time Build Notes

The first `docker compose up --build` will:
1. Install Python packages including `openai-whisper` (~2 min)
2. Download the Whisper `base` model — 74 MB (~1 min depending on connection)
3. Install Node packages for the frontend (~1 min)

Subsequent starts take under 10 seconds.

---

## Whisper Model Options

Edit `docker-compose.yml` to change the model size. Larger = more accurate but slower.

```yaml
environment:
  - WHISPER_MODEL=base   # change this line
```

| Model | Size | Speed | Best for |
|---|---|---|---|
| `tiny` | 39 MB | Very fast | Low-end hardware, English only |
| `base` | 74 MB | Fast | **Recommended** — good Arabic/English |
| `small` | 244 MB | Moderate | Better Arabic accuracy |
| `medium` | 769 MB | Slow | High-accuracy, needs 8 GB RAM |

After changing the model, rebuild:
```bash
docker compose up --build
```

---

## Adding Your Blog Words

1. Open `data/blog_words.txt`
2. Add words from your previous blog posts — one word per line
3. Lines starting with `#` are comments (ignored)
4. Save the file
5. Restart the backend:

```bash
docker compose restart backend
```

### Extracting words from a text file automatically

```bash
# If you have Python installed locally, run this helper:
python extract_blog_words.py your_blog_post.txt
```

This counts word frequencies and appends the top 200 words to `blog_words.txt`.

---

## How Suggestions Are Scored

Each candidate word gets a score based on:

```
score = log(frequency + 1) × 10        ← how often you've used/selected it
      + 25  (if word heard in mic)       ← strong boost from ambient speech
      + log(bigram_freq + 1) × 20       ← how often it follows the prev word
      + (prefix_length / word_length) × 3  ← minor tie-breaker
```

Selected suggestions are persisted to `data/scholar.db` (SQLite) and immediately
reflected in the live trie — no restart needed.

---

## Keyboard Shortcuts

| Key | Action |
|---|---|
| `Tab` | Accept the highlighted suggestion |
| `1` – `6` | Accept suggestion by position |
| `←` / `→` | Navigate between suggestions |
| `Escape` | Dismiss suggestions |

For touch / mouse use: click any suggestion pill directly.

---

## Project Structure

```
islamic-assist/
├── docker-compose.yml
├── README.md
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py          ← FastAPI: /suggest, /learn, /transcribe
│   ├── trie.py          ← Prefix tree with frequency scoring
│   ├── database.py      ← SQLite: word_freq + bigrams tables
│   ├── transcriber.py   ← Whisper wrapper + ffmpeg conversion
│   └── word_list.py     ← 350+ Islamic scholarly seed words
│
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── vite.config.js   ← Proxies /api/* → backend:8000
│   ├── index.html
│   └── src/
│       ├── main.jsx
│       ├── App.jsx       ← Main logic: mic, suggestions, learning
│       ├── App.css       ← Islamic manuscript aesthetic
│       └── components/
│           ├── SuggestionBar.jsx
│           └── MicStatus.jsx
│
└── data/                ← Persisted across restarts (Docker volume)
    ├── blog_words.txt   ← Your custom word list (edit freely)
    └── scholar.db       ← Auto-created SQLite (learned words)
```

---

## Resetting Learned Words

If you want to reset the self-learning to the baseline:

```bash
# Stop the app
docker compose down

# Delete the learned database
del data\scholar.db      # Windows
# or
rm data/scholar.db       # Mac/Linux

# Start again
docker compose up
```

This does NOT affect `blog_words.txt` — those are preserved.

---

## Troubleshooting

**Suggestions not appearing?**
- Backend may still be loading (Whisper model loads on first request). Wait ~30 s.
- Check: http://localhost:8000/health — should return `{"status": "ok"}`

**Mic not working?**
- Browser requires HTTPS OR localhost for microphone access. `localhost:3000` is fine.
- Check browser permissions: click the 🔒 or 🎙️ icon in the address bar.
- If the mic status shows "Error", reload the page and allow mic access.

**App too slow?**
- Change Whisper model to `tiny` in `docker-compose.yml` and rebuild.
- Transcription is off the critical path — suggestions still appear instantly.

**Port conflict?**
- Change `3000:5173` or `8000:8000` in `docker-compose.yml` to free ports.

---

## Privacy

- All audio is transcribed locally by Whisper. Nothing is sent to any cloud service.
- Learned words are stored in `data/scholar.db` on your Surface.
- The Vite dev proxy means the browser never makes cross-origin requests.
