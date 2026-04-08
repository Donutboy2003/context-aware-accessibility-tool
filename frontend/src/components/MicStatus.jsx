import React, { useState } from "react";

/**
 * MicStatus
 * Props:
 *  status       – "idle" | "listening" | "processing" | "error"
 *  transcript   – string (rolling mic transcript)
 */
export default function MicStatus({ status, transcript }) {
  const [expanded, setExpanded] = useState(false);

  const icons = {
    idle:       "○",
    listening:  "●",
    processing: "◌",
    error:      "✕",
  };

  const labels = {
    idle:       "Mic idle",
    listening:  "Listening",
    processing: "Processing…",
    error:      "Mic error — check browser permissions",
  };

  const displayTranscript = transcript.trim().split(" ").slice(-20).join(" ");

  return (
    <div className={`mic-status mic-${status}`}>
      <button
        className="mic-toggle"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
        title="Toggle mic transcript view"
      >
        <span className={`mic-dot ${status === "listening" ? "pulse" : ""}`}>
          {icons[status] ?? "○"}
        </span>
        <span className="mic-label">{labels[status] ?? "Unknown"}</span>
        {transcript && (
          <span className="mic-preview">
            &ldquo;{displayTranscript}&rdquo;
          </span>
        )}
        <span className="mic-chevron">{expanded ? "▲" : "▼"}</span>
      </button>

      {expanded && (
        <div className="mic-expanded">
          <p className="mic-explain">
            Mic context (last 60 s) — used to boost contextually relevant suggestions:
          </p>
          <p className="mic-transcript-text">
            {transcript.trim() || <em>Nothing picked up yet.</em>}
          </p>
        </div>
      )}
    </div>
  );
}
