#!/usr/bin/env python3
"""
scrape_fatwa.py
───────────────
Scrapes all content from fatwa.ca using its sitemaps, extracts the main
article body text, and populates data/blog_words.txt with the most
frequently used words — ready to feed into the writing assistant.

Usage (run from project root):
    pip install requests beautifulsoup4 lxml
    python scrape_fatwa.py

Options:
    --top N         Top N words to save (default: 500)
    --min-len N     Minimum word length (default: 4)
    --min-freq N    Minimum frequency to include (default: 3)
    --delay N       Seconds between requests (default: 1.0)
    --output FILE   Output file (default: data/blog_words.txt)
    --dry-run       Parse sitemaps only, don't fetch pages
"""

import argparse
import re
import time
from collections import Counter
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

# ── Config ─────────────────────────────────────────────────────────────────────

SITEMAPS = [
    "https://fatwa.ca/post-sitemap.xml",
    "https://fatwa.ca/page-sitemap.xml",
]
# We skip category/tag/author sitemaps — they're navigation pages, not content

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# CSS selectors to try for main content (in priority order)
CONTENT_SELECTORS = [
    "article",
    "div.entry-content",
    "div.post-content",
    "div.single-content",
    "div.fatwa-content",
    "div.content-area",
    "main",
    "div#content",
    "div.main-content",
]

# Tags to strip (nav, ads, sidebars, etc.)
NOISE_TAGS = [
    "nav", "header", "footer", "aside", "script", "style",
    "noscript", "iframe", "form", "button", "input",
    "figure", "figcaption", ".sidebar", ".widget", ".menu",
    ".breadcrumb", ".pagination", ".comments", ".related",
    ".share", ".social", ".tags", ".categories", ".author-bio",
]

# English stop words to exclude
STOP_WORDS = {
    "the", "and", "that", "this", "with", "from", "have", "been", "will",
    "they", "their", "there", "when", "what", "which", "who", "whom",
    "about", "also", "some", "into", "than", "then", "them", "were",
    "would", "could", "should", "does", "done", "said", "such", "very",
    "more", "most", "much", "many", "both", "each", "every", "its",
    "your", "their", "our", "his", "her", "those", "these", "because",
    "through", "between", "during", "after", "before", "under", "over",
    "again", "other", "only", "same", "just", "like", "even", "well",
    "back", "any", "good", "here", "where", "upon", "must", "being",
    "know", "think", "make", "made", "take", "gave", "come", "came",
    "went", "thus", "hence", "yet", "shall", "may", "can", "not",
    "but", "for", "are", "was", "has", "had", "him", "her", "all",
    "one", "two", "three", "four", "five", "six", "seven", "eight",
    "nine", "ten", "first", "second", "third", "page", "click", "read",
    "more", "view", "share", "post", "comment", "reply", "search",
    "home", "category", "tag", "author", "date", "year", "month",
    "however", "moreover", "furthermore", "therefore", "consequently",
    "whether", "while", "since", "though", "although", "unless",
    "without", "within", "among", "along", "another", "others",
}


# ── Sitemap parsing ────────────────────────────────────────────────────────────

def fetch_sitemap_urls(sitemap_url: str, session: requests.Session) -> list[str]:
    """Parse a sitemap XML and return all <loc> URLs."""
    try:
        r = session.get(sitemap_url, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.content, "xml")
        urls = [loc.text.strip() for loc in soup.find_all("loc")]
        print(f"  ✓ {sitemap_url} → {len(urls)} URLs")
        return urls
    except Exception as e:
        print(f"  ✗ Failed to fetch sitemap {sitemap_url}: {e}")
        return []


# ── Page scraping ──────────────────────────────────────────────────────────────

def extract_main_text(html: str, url: str) -> str:
    """
    Extract clean article body text from a page.
    Tries multiple selectors and strips navigation/sidebar noise.
    """
    soup = BeautifulSoup(html, "lxml")

    # Remove noise elements
    for selector in NOISE_TAGS:
        for el in soup.select(selector):
            el.decompose()

    # Try content selectors in priority order
    content = None
    for selector in CONTENT_SELECTORS:
        content = soup.select_one(selector)
        if content:
            break

    # Fallback: use body
    if not content:
        content = soup.find("body")
    if not content:
        return ""

    # Get text with newlines between block elements
    text = content.get_text(separator=" ", strip=True)

    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()

    return text


def scrape_page(url: str, session: requests.Session) -> str:
    """Fetch a page and return its main text content."""
    try:
        r = session.get(url, timeout=20)
        r.raise_for_status()

        # Skip non-HTML (PDFs, images, etc.)
        content_type = r.headers.get("content-type", "")
        if "text/html" not in content_type:
            return ""

        return extract_main_text(r.text, url)
    except requests.exceptions.HTTPError as e:
        print(f"  ✗ HTTP {e.response.status_code}: {url}")
        return ""
    except Exception as e:
        print(f"  ✗ Error fetching {url}: {e}")
        return ""


# ── Word extraction ────────────────────────────────────────────────────────────

def extract_words(text: str, min_len: int) -> list[str]:
    """Tokenize text into clean lowercase words."""
    # Split on anything that's not a letter or apostrophe
    words = re.findall(r"[a-zA-Z''\-]{%d,}" % min_len, text)
    cleaned = []
    for w in words:
        w = w.strip("'-").lower()
        if (
            len(w) >= min_len
            and w not in STOP_WORDS
            and not w.startswith("-")
            and not re.match(r"^'+$", w)  # skip bare apostrophes
        ):
            cleaned.append(w)
    return cleaned


# ── Output ────────────────────────────────────────────────────────────────────

def load_existing_words(path: Path) -> set[str]:
    existing = set()
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip().lower()
            if line and not line.startswith("#"):
                existing.add(line)
    return existing


def write_words(
    path: Path,
    counter: Counter,
    top: int,
    min_freq: int,
    existing: set[str],
) -> int:
    """Append new words to blog_words.txt, sorted by frequency."""
    # Filter: min frequency, not already in file, not pure numbers
    new_words = [
        (word, freq)
        for word, freq in counter.most_common(top * 3)
        if freq >= min_freq
        and word not in existing
        and not word.isdigit()
    ][:top]

    if not new_words:
        print("\nNo new words to add.")
        return 0

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write("\n# ── Scraped from fatwa.ca ──────────────────────────────────────\n")
        f.write(f"# {len(new_words)} words extracted (sorted by frequency)\n")
        for word, freq in new_words:
            f.write(f"{word}\n")

    return len(new_words)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Scrape fatwa.ca → blog_words.txt")
    parser.add_argument("--top",      type=int,   default=2000,                    help="Top N words (default 500)")
    parser.add_argument("--min-len",  type=int,   default=3,                      help="Min word length (default 4)")
    parser.add_argument("--min-freq", type=int,   default=1,                      help="Min frequency (default 3)")
    parser.add_argument("--delay",    type=float, default=0.3,                    help="Delay between requests in seconds (default 1.0)")
    parser.add_argument("--output",   type=str,   default="data/blog_words.txt",  help="Output file")
    parser.add_argument("--dry-run",  action="store_true",                        help="Parse sitemaps only, don't scrape pages")
    args = parser.parse_args()

    output_path = Path(args.output)

    print("=" * 60)
    print("  fatwa.ca Scraper → blog_words.txt")
    print("=" * 60)

    session = requests.Session()
    session.headers.update(HEADERS)

    # ── Step 1: Collect all URLs from sitemaps ──
    print(f"\n[1/3] Fetching sitemaps...")
    all_urls: list[str] = []
    for sitemap_url in SITEMAPS:
        urls = fetch_sitemap_urls(sitemap_url, session)
        all_urls.extend(urls)

    # Deduplicate
    all_urls = list(dict.fromkeys(all_urls))
    print(f"\n  Total unique URLs to scrape: {len(all_urls)}")

    if args.dry_run:
        print("\n[DRY RUN] Skipping page scraping. URLs found:")
        for u in all_urls[:20]:
            print(f"  {u}")
        if len(all_urls) > 20:
            print(f"  ... and {len(all_urls) - 20} more")
        return

    # ── Step 2: Scrape each page ──
    print(f"\n[2/3] Scraping {len(all_urls)} pages (delay={args.delay}s between requests)...")
    print(f"  Estimated time: {len(all_urls) * args.delay / 60:.1f} minutes\n")

    counter: Counter = Counter()
    success = 0
    skipped = 0

    for i, url in enumerate(all_urls, 1):
        print(f"  [{i:4d}/{len(all_urls)}] {url[:70]}", end=" ", flush=True)

        text = scrape_page(url, session)
        if text:
            words = extract_words(text, args.min_len)
            counter.update(words)
            print(f"→ {len(words)} words")
            success += 1
        else:
            print("→ skipped")
            skipped += 1

        # Polite delay between requests
        if i < len(all_urls):
            time.sleep(args.delay)

    print(f"\n  Done. {success} pages scraped, {skipped} skipped.")
    print(f"  Unique words found: {len(counter)}")

    # ── Step 3: Write to blog_words.txt ──
    print(f"\n[3/3] Writing top {args.top} words (min freq={args.min_freq}) to {output_path}...")

    existing = load_existing_words(output_path)
    n_added = write_words(output_path, counter, args.top, args.min_freq, existing)

    print(f"\n  ✓ Added {n_added} new words to {output_path}")

    if n_added > 0:
        print("\n  Top 20 most frequent new words:")
        new_words_preview = [
            (w, f) for w, f in counter.most_common(200)
            if w not in existing and f >= args.min_freq
        ][:20]
        for word, freq in new_words_preview:
            print(f"    {word:<25} (freq: {freq})")

    print(f"""
  Next step — restart the backend to apply new words:
    docker compose restart backend
""")


if __name__ == "__main__":
    main()