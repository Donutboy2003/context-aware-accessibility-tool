import React from "react";

export default function SuggestionBar({ suggestions, activeIndex, onSelect, onSetActive }) {
  // Always render — never return null — so the layout height stays constant
  const hasResults = suggestions.length > 0;

  return (
    <div className={`suggestion-bar ${hasResults ? "has-suggestions" : "empty"}`} role="listbox" aria-label="Word suggestions">
      <div className="suggestion-hint">
        {hasResults
          ? <><kbd>Tab</kbd> accept &nbsp;·&nbsp; <kbd>1</kbd>–<kbd>{Math.min(suggestions.length, 6)}</kbd> select &nbsp;·&nbsp; <kbd>←</kbd><kbd>→</kbd> navigate</>
          : <span className="hint-idle">Start typing for suggestions…</span>
        }
      </div>
      <div className="suggestion-pills">
        {hasResults
          ? suggestions.map((word, idx) => (
              <button
                key={word + idx}
                className={`suggestion-pill ${idx === activeIndex ? "active" : ""}`}
                role="option"
                aria-selected={idx === activeIndex}
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => onSelect(word)}
                onMouseEnter={() => onSetActive(idx)}
              >
                <span className="pill-number">{idx + 1}</span>
                <span className="pill-word">{word}</span>
              </button>
            ))
          : <div className="pills-placeholder" aria-hidden="true" />
        }
      </div>
    </div>
  );
}