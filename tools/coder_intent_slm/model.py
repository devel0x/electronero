"""A tiny intent-focused language model for coding automation.

This is intentionally small and deterministic so it can run standalone without
third-party dependencies.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import math
import re
from typing import Iterable

TOKEN_RE = re.compile(r"[a-zA-Z_][a-zA-Z0-9_+#.-]*")


@dataclass(frozen=True)
class IntentPrediction:
    intent: str
    confidence: float
    scores: dict[str, float]


class TinyIntentModel:
    """Multinomial Naive Bayes classifier for developer intents."""

    def __init__(self) -> None:
        self._token_counts: dict[str, Counter[str]] = defaultdict(Counter)
        self._total_counts: dict[str, int] = defaultdict(int)
        self._doc_counts: Counter[str] = Counter()
        self._vocab: set[str] = set()
        self._trained = False

    @staticmethod
    def tokenize(text: str) -> list[str]:
        return [t.lower() for t in TOKEN_RE.findall(text)]

    def fit(self, samples: Iterable[tuple[str, str]]) -> None:
        for intent, text in samples:
            tokens = self.tokenize(text)
            if not tokens:
                continue
            self._doc_counts[intent] += 1
            self._token_counts[intent].update(tokens)
            self._total_counts[intent] += len(tokens)
            self._vocab.update(tokens)
        self._trained = bool(self._doc_counts)

    def predict(self, text: str) -> IntentPrediction:
        if not self._trained:
            raise RuntimeError("Model has not been trained. Call fit() first.")

        tokens = self.tokenize(text)
        if not tokens:
            fallback = self._doc_counts.most_common(1)[0][0]
            return IntentPrediction(fallback, 0.0, {fallback: 0.0})

        total_docs = sum(self._doc_counts.values())
        vocab_size = max(len(self._vocab), 1)

        log_scores: dict[str, float] = {}
        for intent in self._doc_counts:
            prior = self._doc_counts[intent] / total_docs
            log_prob = math.log(prior)
            denom = self._total_counts[intent] + vocab_size
            for token in tokens:
                count = self._token_counts[intent][token]
                log_prob += math.log((count + 1) / denom)
            log_scores[intent] = log_prob

        best_intent = max(log_scores, key=log_scores.get)

        # Convert to stable probabilities.
        max_log = max(log_scores.values())
        exp_scores = {k: math.exp(v - max_log) for k, v in log_scores.items()}
        normalizer = sum(exp_scores.values()) or 1.0
        scores = {k: v / normalizer for k, v in exp_scores.items()}

        return IntentPrediction(
            intent=best_intent,
            confidence=scores[best_intent],
            scores=scores,
        )
