"""Unit tests for synthetic data generation (no AWS calls)."""

from __future__ import annotations

import json

from data_curator.generate import (
    make_csv,
    make_html_faq,
    make_jsonl,
    make_markdown_policy,
)


class TestCsvGeneration:
    def test_header_present(self):
        csv = make_csv(num_rows=5)
        lines = csv.strip().split("\n")
        assert "sku,name,category,brand,price_inr,stock" in lines[0]

    def test_row_count(self):
        csv = make_csv(num_rows=10)
        lines = csv.strip().split("\n")
        assert len(lines) == 11  # 1 header + 10 data rows

    def test_zero_rows(self):
        csv = make_csv(num_rows=0)
        lines = csv.strip().split("\n")
        assert len(lines) == 1  # header only


class TestJsonlGeneration:
    def test_each_line_valid_json(self):
        jsonl = make_jsonl(num_records=10)
        for line in jsonl.strip().split("\n"):
            obj = json.loads(line)  # raises if invalid
            assert "order_id" in obj
            assert "items" in obj
            assert isinstance(obj["items"], list)


class TestMarkdownPolicy:
    def test_has_sections(self):
        md = make_markdown_policy()
        assert "# Returns & Refunds Policy" in md
        assert "## Overview" in md
        assert "## Return window" in md


class TestHtmlFaq:
    def test_has_questions(self):
        html = make_html_faq()
        assert "<!DOCTYPE html>" in html
        assert "<h3>" in html
        assert "How do I track my order?" in html
