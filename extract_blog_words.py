#!/usr/bin/env python3
"""
extract_blog_words.py
─────────────────────
Extract the most frequently used words from your blog posts and append them
to data/blog_words.txt for use in the writing assistant.

Usage:
    python extract_blog_words.py path/to/blog_post.txt [another.txt ...]
    python extract_blog_words.py --dir path/to/blog_folder/

Options:
    --top N         Number of top words to extract (default: 200)
    --min-len N     Minimum word length to include (default: 4)
    --output FILE   Output file (default: data/blog_words.txt)
"""

import argparse
import os
import re
import sys
from collections import Counter
from pathlib import Path

# ── Common English stop words to exclude ──────────────────────────────────────
STOP_WORDS = {
    "the", "and", "that", "this", "with", "from", "have", "been", "will",
    "they", "their", "there", "when", "what", "which", "who", "whom",
    "about", "also", "some", "into", "than", "then", "them", "were",
    "would", "could", "should", "does", "done", "said", "such", "very",
    "more", "most", "much", "many", "both", "each", "every", "its",
    "your", "their", "our", "his", "her", "its", "those", "these",
    "because", "through", "between", "during", "after", "before",
    "under", "over", "again", "other", "only", "same", "just", "like",
    "even", "well", "back", "any", "good", "here", "where", "upon",
    "must", "being", "know", "think", "make", "made", "take", "gave",
    "come", "came", "went", "said", "told", "thus", "hence", "yet",
}


def extract_words(text: str, min_len: int) -> list[str]:
    # Remove URLs, numbers, punctuation; keep letters and apostrophes
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"\d+", " ", text)
    words = re.findall(r"[a-zA-Z''\-]{%d,}" % min_len, text)
    return [
        w.strip("'-").lower()
        for w in words
        if len(w.strip("'-")) >= min_len
        and w.strip("'-").lower() not in STOP_WORDS
        and not w.startswith("-")
    ]


def main():
    parser = argparse.ArgumentParser(description="Extract blog words for writing assistant.")
    parser.add_argument("files", nargs="*", help="Text files to process")
    parser.add_argument("--dir", help="Directory of text files to process")
    parser.add_argument("--top", type=int, default=200, help="Top N words (default 200)")
    parser.add_argument("--min-len", type=int, default=4, help="Min word length (default 4)")
    parser.add_argument("--output", default="data/blog_words.txt", help="Output file")
    args = parser.parse_args()

    input_files: list[Path] = []

    if args.dir:
        d = Path(args.dir)
        input_files.extend(d.glob("*.txt"))
        input_files.extend(d.glob("*.md"))

    for f in args.files:
        input_files.append(Path(f))

    if not input_files:
        print("No input files found. Provide file paths or use --dir.")
        sys.exit(1)

    counter: Counter = Counter()

    for path in input_files:
        if not path.exists():
            print(f"⚠  Skipping (not found): {path}")
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        words = extract_words(text, args.min_len)
        counter.update(words)
        print(f"✓  {path.name}: {len(words)} words extracted")

    top_words = [word for word, _ in counter.most_common(args.top)]

    # Load existing words so we don't duplicate
    output_path = Path(args.output)
    existing: set[str] = set()
    if output_path.exists():
        for line in output_path.read_text().splitlines():
            stripped = line.strip().lower()
            if stripped and not stripped.startswith("#"):
                existing.add(stripped)

    new_words = [w for w in top_words if w not in existing]

    if not new_words:
        print("\nNo new words to add (all already present in blog_words.txt).")
        return

    # Append to output file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "a", encoding="utf-8") as f:
        f.write(f"\n# Extracted from: {', '.join(p.name for p in input_files)}\n")
        for word in new_words:
            f.write(word + "\n")

    print(f"\n✓ Added {len(new_words)} new words to {output_path}")
    print(f"  Top 10 new words: {', '.join(new_words[:10])}")
    print(f"\nRestart the backend to apply: docker compose restart backend")


if __name__ == "__main__":
    main()
