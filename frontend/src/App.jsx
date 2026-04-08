import React, { useCallback, useEffect, useRef, useState } from "react";
import MicStatus from "./components/MicStatus";
import SuggestionBar from "./components/SuggestionBar";

const API = "/api";
const CHUNK_INTERVAL_MS = 5000;   // send audio to backend every 5 s
const DEBOUNCE_MS = 150;          // wait after keypress before fetching suggestions
const MIC_WINDOW_WORDS = 120;     // keep rolling window of N words from mic

// ── Helpers ────────────────────────────────────────────────────────────────────

/** Extract the word currently being typed and preceding context words. */
function parseTextContext(text, cursorPos) {
  const before = text.substring(0, cursorPos);
  const after  = text.substring(cursorPos);

  // Find where the current token starts
  const lastSpace = before.lastIndexOf(" ");
  const currentWord = before.substring(lastSpace + 1);

  // Previous words = everything before the current word
  const prevText = lastSpace >= 0 ? before.substring(0, lastSpace) : "";
  const prevWords = prevText.split(/\s+/).filter(Boolean);

  return { currentWord, prevWords, after };
}

// ── App ─────────────────────────────────────────────────────────────────────────

export default function App() {
  const [text, setText] = useState("");
  const [suggestions, setSuggestions] = useState([]);
  const [activeIdx, setActiveIdx] = useState(0);
  const [micStatus, setMicStatus] = useState("idle");
  const [micTranscript, setMicTranscript] = useState("");
  const [fontSize, setFontSize] = useState(20);
  const [wordCount, setWordCount] = useState(0);
  const [lastSelected, setLastSelected] = useState(null); // for status display

  const textareaRef     = useRef(null);
  const micTranscriptRef = useRef("");  // mutable ref for use inside closures
  const debounceTimer   = useRef(null);
  const recorderRef     = useRef(null);
  const streamRef       = useRef(null);

  // Keep ref in sync with state
  useEffect(() => {
    micTranscriptRef.current = micTranscript;
  }, [micTranscript]);

  // ── Word count ──────────────────────────────────────────────────────────────
  useEffect(() => {
    setWordCount(text.trim() === "" ? 0 : text.trim().split(/\s+/).length);
  }, [text]);

  // ── Fetch suggestions (debounced) ──────────────────────────────────────────
  const fetchSuggestions = useCallback(async (value, cursorPos) => {
    const { currentWord, prevWords } = parseTextContext(value, cursorPos);

    if (currentWord.length === 0) {
      setSuggestions([]);
      return;
    }

    try {
      const res = await fetch(`${API}/suggest`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prefix:        currentWord,
          prev_words:    prevWords.slice(-4),
          mic_transcript: micTranscriptRef.current,
        }),
      });
      if (!res.ok) return;
      const data = await res.json();
      setSuggestions(data.suggestions ?? []);
      setActiveIdx(0);
    } catch {
      // Backend not ready yet — fail silently
    }
  }, []);

  const scheduleSuggestions = useCallback((value, cursorPos) => {
    clearTimeout(debounceTimer.current);
    debounceTimer.current = setTimeout(() => {
      fetchSuggestions(value, cursorPos);
    }, DEBOUNCE_MS);
  }, [fetchSuggestions]);

  // ── Select a suggestion ────────────────────────────────────────────────────
  const selectSuggestion = useCallback(async (word) => {
    const ta = textareaRef.current;
    if (!ta) return;

    const cursorPos = ta.selectionStart;
    const { currentWord, prevWords, after } = parseTextContext(text, cursorPos);
    const prevWord = prevWords[prevWords.length - 1] ?? null;

    // Replace the in-progress word with the selected suggestion + space
    const before = text.substring(0, cursorPos - currentWord.length);
    const newText = before + word + " " + after.trimStart();
    setText(newText);
    setSuggestions([]);
    setLastSelected(word);

    // Move cursor to after the inserted word + space
    const newCursor = before.length + word.length + 1;
    setTimeout(() => {
      ta.setSelectionRange(newCursor, newCursor);
      ta.focus();
    }, 0);

    // Teach the model
    try {
      await fetch(`${API}/learn`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ selected_word: word, prev_word: prevWord }),
      });
    } catch {
      // Fire-and-forget — not critical
    }
  }, [text]);

  // ── Handle textarea changes ────────────────────────────────────────────────
  const handleChange = (e) => {
    setText(e.target.value);
    scheduleSuggestions(e.target.value, e.target.selectionStart);
  };

  // ── Keyboard shortcuts ─────────────────────────────────────────────────────
  const handleKeyDown = (e) => {
    if (!suggestions.length) return;

    if (e.key === "Tab") {
      e.preventDefault();
      selectSuggestion(suggestions[activeIdx]);
      return;
    }

    // Number keys 1–6 pick suggestion by position
    if (e.key >= "1" && e.key <= "6") {
      const idx = parseInt(e.key, 10) - 1;
      if (suggestions[idx]) {
        e.preventDefault();
        selectSuggestion(suggestions[idx]);
        return;
      }
    }

    if (e.key === "ArrowRight") {
      e.preventDefault();
      setActiveIdx((i) => Math.min(i + 1, suggestions.length - 1));
      return;
    }
    if (e.key === "ArrowLeft") {
      e.preventDefault();
      setActiveIdx((i) => Math.max(i - 1, 0));
      return;
    }

    // Escape clears suggestions
    if (e.key === "Escape") {
      setSuggestions([]);
    }
  };

  // ── Mic recording ──────────────────────────────────────────────────────────
  useEffect(() => {
    let stream;
    let intervalId;
    let active = true;

    const sendChunk = async (blob) => {
      if (!active || blob.size < 1000) return;
      setMicStatus("processing");
      const form = new FormData();
      form.append("audio", blob, "chunk.webm");
      try {
        const res = await fetch(`${API}/transcribe`, { method: "POST", body: form });
        if (res.ok) {
          const { transcript } = await res.json();
          if (transcript) {
            setMicTranscript((prev) => {
              const words = (prev + " " + transcript).trim().split(/\s+/);
              return words.slice(-MIC_WINDOW_WORDS).join(" ");
            });
          }
        }
      } catch {
        // Transcription failed — keep going
      } finally {
        if (active) setMicStatus("listening");
      }
    };

    const recordChunk = (stream) => {
      // Each call creates a fresh recorder → fresh complete WebM file ffmpeg can parse
      const chunks = [];
      let mimeType = "audio/webm;codecs=opus";
      if (!MediaRecorder.isTypeSupported(mimeType)) mimeType = "audio/webm";
      const recorder = new MediaRecorder(stream, { mimeType });
      recorder.ondataavailable = (e) => { if (e.data.size > 0) chunks.push(e.data); };
      recorder.onstop = () => {
        const blob = new Blob(chunks, { type: mimeType });
        sendChunk(blob);
      };
      recorder.start();
      return recorder;
    };

    const start = async () => {
      try {
        stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        streamRef.current = stream;
        setMicStatus("listening");

        let currentRecorder = recordChunk(stream);

        intervalId = setInterval(() => {
          if (!active) return;
          // Stop current recorder (triggers onstop → sendChunk), start fresh one
          currentRecorder.stop();
          currentRecorder = recordChunk(stream);
        }, CHUNK_INTERVAL_MS);

      } catch (err) {
        console.error("Mic access denied:", err);
        setMicStatus("error");
      }
    };

    start();

    return () => {
      active = false;
      clearInterval(intervalId);
      if (stream) stream.getTracks().forEach((t) => t.stop());
    };
  }, []);

  // ── Copy to clipboard ──────────────────────────────────────────────────────
  const copyText = () => {
    navigator.clipboard.writeText(text).catch(() => {});
  };

  const clearText = () => {
    if (window.confirm("Clear all text?")) {
      setText("");
      setSuggestions([]);
      textareaRef.current?.focus();
    }
  };

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="app">
      {/* ── Header ── */}
      <header className="app-header">
        <div className="header-left">
          <span className="header-ornament">❧</span>
          <div>
            <h1 className="header-title">Scholar's Writing Assistant</h1>
            <p className="header-subtitle">Islamic scholarly composition tool</p>
          </div>
        </div>
        <div className="header-right">
          <div className="font-control">
            <label htmlFor="font-size">Text size</label>
            <input
              id="font-size"
              type="range"
              min="14"
              max="36"
              value={fontSize}
              onChange={(e) => setFontSize(Number(e.target.value))}
            />
            <span className="font-size-val">{fontSize}px</span>
          </div>
          <MicStatus status={micStatus} transcript={micTranscript} />
        </div>
      </header>

      {/* ── Suggestion Bar ── */}
      <SuggestionBar
        suggestions={suggestions}
        activeIndex={activeIdx}
        onSelect={selectSuggestion}
        onSetActive={setActiveIdx}
      />

      {/* ── Text Area ── */}
      <main className="editor-main">
        <textarea
          ref={textareaRef}
          className="editor-textarea"
          value={text}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          style={{ fontSize: `${fontSize}px`, lineHeight: 1.8 }}
          placeholder="Begin writing here… suggestions will appear as you type."
          spellCheck="true"
          autoFocus
          aria-label="Writing area"
        />
      </main>

      {/* ── Footer ── */}
      <footer className="app-footer">
        <div className="footer-left">
          <span className="word-count">{wordCount} word{wordCount !== 1 ? "s" : ""}</span>
          {lastSelected && (
            <span className="last-selected">✓ &ldquo;{lastSelected}&rdquo; learned</span>
          )}
        </div>
        <div className="footer-right">
          <button className="footer-btn" onClick={copyText}>Copy text</button>
          <button className="footer-btn footer-btn-danger" onClick={clearText}>Clear</button>
        </div>
      </footer>
    </div>
  );
}