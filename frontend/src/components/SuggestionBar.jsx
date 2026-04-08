import React from "react";

/**
 * SuggestionBar
 * Props:
 *  suggestions   – string[]
 *  activeIndex   – number (keyboard-highlighted index)
 *  onSelect      – (word: string) => void
 *  onSetActive   – (index: number) => void
 */
export default function SuggestionBar({ suggestions, activeIndex, onSelect, onSetActive }) {
  if (!suggestions.length) return null;

  return (
    <div className="suggestion-bar" role="listbox" aria-label="Word suggestions">
      <div className="suggestion-hint">
        <kbd>Tab</kbd> accept &nbsp;·&nbsp; <kbd>1</kbd>–<kbd>{Math.min(suggestions.length, 6)}</kbd> select &nbsp;·&nbsp; <kbd>←</kbd><kbd>→</kbd> navigate
      </div>
      <div className="suggestion-pills">
        {suggestions.map((word, idx) => (
          <button
            key={word + idx}
            className={`suggestion-pill ${idx === activeIndex ? "active" : ""}`}
            role="option"
            aria-selected={idx === activeIndex}
            // mousedown prevents textarea blur before click fires
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => onSelect(word)}
            onMouseEnter={() => onSetActive(idx)}
          >
            <span className="pill-number">{idx + 1}</span>
            <span className="pill-word">{word}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
