"""Classifier.

Assigns a category and tags to each chunk. Phase 1 uses a simple keyword-based
classifier for determinism and zero cost. Phase 3 will swap in DSPy-optimized
LLM-based classification with self-learning from user feedback.

Categories are loaded from `config/classifier/categories.yaml` so they can be
extended without code changes.
"""

from __future__ import annotations

import time
from pathlib import Path

import yaml

from src.common import (
    BaseLambda,
    Classification,
    ClassifiedChunk,
    EmbeddedChunk,
    JobContext,
    stage,
)

CLASSIFIER_VERSION = "rule-based-1.0.0"


def _load_default_categories() -> dict[str, list[str]]:
    """Load categories from config/classifier/categories.yaml, with fallback."""
    default_path = Path(__file__).parent.parent / "config" / "classifier" / "categories.yaml"
    if default_path.exists():
        with Path(default_path).open() as f:
            data = yaml.safe_load(f) or {}
            return data.get("categories", {})
    # Fallback hardcoded set
    return {
        "product-listing": ["product", "sku", "price", "buy", "cart", "shop"],
        "financial-report": ["revenue", "earnings", "fiscal", "10-k", "quarterly", "ebitda"],
        "legal-contract": ["agreement", "party", "clause", "whereas", "shall", "jurisdiction"],
        "technical-doc": ["api", "endpoint", "function", "parameter", "return", "schema"],
        "support-faq": ["how to", "question", "answer", "help", "support"],
        "policy-document": ["policy", "compliance", "gdpr", "hipaa", "regulation"],
        "general": [],
    }


@stage(name="classify", input_model=EmbeddedChunk, output_model=ClassifiedChunk)
class RuleBasedClassifier(BaseLambda):
    """Phase 1: rule-based classifier using keyword matching.

    Phase 3: will be replaced with DSPy-optimized classifier that learns
    from user feedback.
    """

    def setup(self) -> None:
        self.categories = _load_default_categories()

    def handle(self, ctx: JobContext, inp: EmbeddedChunk) -> ClassifiedChunk:
        start = time.perf_counter()
        text_lower = inp.text.lower()

        # Score each category
        scores: dict[str, int] = {}
        matched_tags: dict[str, list[str]] = {}
        for category, keywords in self.categories.items():
            count = 0
            matched = []
            for kw in keywords:
                if kw.lower() in text_lower:
                    count += 1
                    matched.append(kw)
            scores[category] = count
            matched_tags[category] = matched

        # Pick the best
        if not scores or max(scores.values()) == 0:
            best_category = "general"
            confidence = 0.5
            tags: list[str] = []
        else:
            best_category = max(scores, key=lambda k: scores[k])
            best_count = scores[best_category]
            total_keywords = len(self.categories[best_category]) or 1
            confidence = min(0.99, best_count / total_keywords)
            tags = matched_tags[best_category][:5]  # top 5

        classification = Classification(
            category=best_category,
            tags=tags,
            confidence=round(confidence, 3),
            classifier_version=CLASSIFIER_VERSION,
            model_used="rule-based",
        )

        self.log.info(
            "classifier.complete",
            job_id=ctx.job_id,
            chunk_id=inp.chunk_id,
            category=best_category,
            confidence=confidence,
            duration_ms=int((time.perf_counter() - start) * 1000),
        )

        # Carry every field forward from the input rather than listing them.
        # Hand-listed constructions silently dropped any field added to the
        # upstream model -- that is how source_bucket/source_key vanished
        # between Chunk and Route.
        return ClassifiedChunk(
            **inp.to_dict(),
            classification=classification,
        )
