"""Unit tests for YAML config files."""

from __future__ import annotations

from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).parent.parent.parent / "config"


class TestChunkerConfigs:
    def test_default_exists(self):
        path = CONFIG_DIR / "chunkers" / "default.yaml"
        assert path.exists()
        with open(path) as f:
            data = yaml.safe_load(f)
        assert "target_tokens" in data
        assert "max_tokens" in data
        assert data["max_tokens"] > data["target_tokens"]


class TestEmbedderConfigs:
    def test_titan_v2_exists(self):
        path = CONFIG_DIR / "embedders" / "titan-v2.yaml"
        assert path.exists()
        with open(path) as f:
            data = yaml.safe_load(f)
        assert data["model_id"] == "amazon.titan-embed-text-v2:0"
        assert data["dimensions"] == 1024
        assert data["region"] == "ap-south-1"


class TestClassifierConfig:
    def test_categories_exist(self):
        path = CONFIG_DIR / "classifier" / "categories.yaml"
        assert path.exists()
        with open(path) as f:
            data = yaml.safe_load(f)
        assert "categories" in data
        assert "general" in data["categories"]
        # Every category should have a list of keywords
        for cat, keywords in data["categories"].items():
            assert isinstance(keywords, list)


class TestParserConfigs:
    def test_default_exists(self):
        path = CONFIG_DIR / "parsers" / "default.yaml"
        assert path.exists()
