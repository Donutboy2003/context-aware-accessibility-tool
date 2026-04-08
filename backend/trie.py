class TrieNode:
    __slots__ = ("children", "is_end", "word", "frequency")

    def __init__(self):
        self.children: dict[str, "TrieNode"] = {}
        self.is_end: bool = False
        self.word: str | None = None
        self.frequency: int = 1


class Trie:
    def __init__(self):
        self.root = TrieNode()

    def insert(self, word: str, frequency: int = 1) -> None:
        node = self.root
        for char in word.lower():
            if char not in node.children:
                node.children[char] = TrieNode()
            node = node.children[char]
        if node.is_end:
            # Word already exists — take the higher frequency
            node.frequency = max(node.frequency, frequency)
        else:
            node.is_end = True
            node.word = word
            node.frequency = frequency

    def get_frequency(self, word: str) -> int:
        node = self.root
        for char in word.lower():
            if char not in node.children:
                return 0
            node = node.children[char]
        return node.frequency if node.is_end else 0

    def boost_frequency(self, word: str, amount: int = 1) -> None:
        node = self.root
        for char in word.lower():
            if char not in node.children:
                return
            node = node.children[char]
        if node.is_end:
            node.frequency += amount

    def search_prefix(self, prefix: str, max_results: int = 20) -> list[tuple[str, int]]:
        """Return (word, frequency) pairs for all words matching prefix, sorted by freq desc."""
        node = self.root
        for char in prefix.lower():
            if char not in node.children:
                return []
            node = node.children[char]

        results: list[tuple[str, int]] = []
        # Iterative DFS — stack holds nodes to visit
        stack = [node]
        while stack and len(results) < max_results * 3:
            curr = stack.pop()
            if curr.is_end and curr.word:
                results.append((curr.word, curr.frequency))
            # Push children sorted by frequency descending so high-freq branches explored first
            for child in sorted(curr.children.values(), key=lambda n: -n.frequency):
                stack.append(child)

        results.sort(key=lambda x: -x[1])
        return results[:max_results]
