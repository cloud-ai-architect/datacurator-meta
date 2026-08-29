"""Unit tests for the semantic chunker."""

from __future__ import annotations

from src.chunker import (
    ChunkerConfig,
    estimate_tokens,
    split_into_paragraphs,
    split_into_sentences,
)


class TestEstimateTokens:
    def test_short_text(self):
        assert estimate_tokens("Hello world") >= 1

    def test_empty_text(self):
        assert estimate_tokens("") == 1

    def test_long_text(self):
        text = "This is a longer piece of text that should have more tokens. " * 100
        tokens = estimate_tokens(text)
        # ~4 chars per token, so ~100*55/4 = 1375
        assert 1000 < tokens < 2000


class TestSplitSentences:
    def test_basic(self):
        text = "First sentence. Second sentence. Third sentence."
        sentences = split_into_sentences(text)
        assert len(sentences) == 3

    def test_empty(self):
        assert split_into_sentences("") == []

    def test_no_punctuation(self):
        # Falls back to single sentence
        sentences = split_into_sentences("just one sentence")
        assert len(sentences) >= 1


class TestSplitParagraphs:
    def test_basic(self):
        text = "Para 1.\n\nPara 2.\n\nPara 3."
        paragraphs = split_into_paragraphs(text)
        assert len(paragraphs) == 3

    def test_empty(self):
        assert split_into_paragraphs("") == []


class TestChunkerConfig:
    def test_defaults(self):
        config = ChunkerConfig()
        assert config.target_tokens == 300
        assert config.min_tokens == 100
        assert config.max_tokens == 500
        assert config.overlap_tokens == 50

    def test_custom(self):
        config = ChunkerConfig(target_tokens=100, max_tokens=200)
        assert config.target_tokens == 100
        assert config.max_tokens == 200
