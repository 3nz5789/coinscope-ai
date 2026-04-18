"""
FinBERT Sentiment Filter — Placeholder / Mock Implementation

In production this would call a FinBERT inference endpoint or
HuggingFace transformers to score crypto-related news headlines.
The MockSentimentFilter below always allows trades through so the
rest of the pipeline can run without an NLP service configured.
"""

from __future__ import annotations
from typing import Tuple


class MockSentimentFilter:
    """
    Stub sentiment filter used when FinBERT is unavailable.
    Never blocks a signal — returns (False, 'sentiment: mock/ok').
    """

    def __init__(self):
        self.enabled = False

    def should_block(self, direction: str, headlines: list) -> Tuple[bool, str]:
        """
        Args:
            direction: 'LONG' | 'SHORT'
            headlines: list of recent news headline strings (unused in mock)
        Returns:
            (blocked: bool, reason: str)
        """
        return False, "sentiment: mock/ok (FinBERT not configured)"

    def score(self, text: str) -> float:
        """Return neutral sentiment score (0.0) for any text."""
        return 0.0


class FinBERTSentimentFilter(MockSentimentFilter):
    """
    Production FinBERT sentiment filter.
    Requires:  pip install transformers torch
    Set env var FINBERT_MODEL_PATH or it falls back to mock.
    """

    def __init__(self, model_path: str = "ProsusAI/finbert"):
        import os
        self.model_path = os.getenv("FINBERT_MODEL_PATH", model_path)
        self._pipeline = None
        self.enabled = True

    def _load(self):
        if self._pipeline is None:
            try:
                from transformers import pipeline
                self._pipeline = pipeline(
                    "text-classification",
                    model=self.model_path,
                    top_k=None,
                )
            except Exception as e:
                print(f"[FinBERT] Could not load model: {e}. Using mock.")
                self._pipeline = None

    def score(self, text: str) -> float:
        """
        Returns sentiment score in [-1, +1].
        Positive = bullish, Negative = bearish.
        """
        self._load()
        if self._pipeline is None:
            return 0.0
        results = self._pipeline(text[:512])[0]
        scores = {r["label"]: r["score"] for r in results}
        return scores.get("positive", 0.5) - scores.get("negative", 0.5)

    def should_block(self, direction: str, headlines: list) -> tuple:
        if not headlines:
            return False, "sentiment: no headlines"
        avg = sum(self.score(h) for h in headlines) / len(headlines)
        if direction == "LONG" and avg < -0.3:
            return True, f"sentiment: bearish ({avg:.2f})"
        if direction == "SHORT" and avg > 0.3:
            return True, f"sentiment: bullish ({avg:.2f})"
        return False, f"sentiment: neutral ({avg:.2f})"
