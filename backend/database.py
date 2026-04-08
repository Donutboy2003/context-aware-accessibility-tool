import sqlite3
import os
import threading


class Database:
    def __init__(self, path: str):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self._lock = threading.Lock()
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            self.conn.executescript("""
                CREATE TABLE IF NOT EXISTS word_freq (
                    word      TEXT PRIMARY KEY,
                    frequency INTEGER NOT NULL DEFAULT 1,
                    last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS bigrams (
                    word1     TEXT NOT NULL,
                    word2     TEXT NOT NULL,
                    frequency INTEGER NOT NULL DEFAULT 1,
                    PRIMARY KEY (word1, word2)
                );

                CREATE INDEX IF NOT EXISTS idx_bigrams_word1 ON bigrams(word1);
            """)
            self.conn.commit()

    # ── word frequency ──────────────────────────────────────────────────────────

    def get_all_words(self) -> list[tuple[str, int]]:
        cur = self.conn.execute("SELECT word, frequency FROM word_freq")
        return [(r["word"], r["frequency"]) for r in cur.fetchall()]

    def increment_word(self, word: str, amount: int = 1) -> None:
        with self._lock:
            self.conn.execute(
                """
                INSERT INTO word_freq (word, frequency) VALUES (?, ?)
                ON CONFLICT(word) DO UPDATE SET
                    frequency = frequency + excluded.frequency,
                    last_used = CURRENT_TIMESTAMP
                """,
                (word.lower(), amount),
            )
            self.conn.commit()

    # ── bigram frequency ────────────────────────────────────────────────────────

    def get_bigram_freq(self, word1: str, word2: str) -> int:
        cur = self.conn.execute(
            "SELECT frequency FROM bigrams WHERE word1=? AND word2=?",
            (word1.lower(), word2.lower()),
        )
        row = cur.fetchone()
        return row["frequency"] if row else 0

    def get_top_bigrams(self, word1: str, limit: int = 10) -> list[tuple[str, int]]:
        """Return the most frequent words that follow word1."""
        cur = self.conn.execute(
            "SELECT word2, frequency FROM bigrams WHERE word1=? ORDER BY frequency DESC LIMIT ?",
            (word1.lower(), limit),
        )
        return [(r["word2"], r["frequency"]) for r in cur.fetchall()]

    def increment_bigram(self, word1: str, word2: str, amount: int = 1) -> None:
        with self._lock:
            self.conn.execute(
                """
                INSERT INTO bigrams (word1, word2, frequency) VALUES (?, ?, ?)
                ON CONFLICT(word1, word2) DO UPDATE SET frequency = frequency + excluded.frequency
                """,
                (word1.lower(), word2.lower(), amount),
            )
            self.conn.commit()
