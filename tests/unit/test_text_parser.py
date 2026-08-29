"""Unit tests for the plain-text / Markdown parser."""

from __future__ import annotations

from src.parsers.text import TextParser, _decode


class TestDecode:
    def test_utf8(self):
        text, enc, warnings = _decode(b"hello world")
        assert text == "hello world"
        assert enc == "utf-8"
        assert warnings == []

    def test_utf8_bom_detected_via_bom_table(self):
        text, enc, warnings = _decode("cafe".encode("utf-8-sig"))
        assert text.lstrip(chr(0xFEFF)) == "cafe"
        assert enc == "utf-8-sig"
        assert warnings == []

    def test_utf16_bom_is_honoured(self):
        text, enc, _ = _decode("hello".encode("utf-16"))
        assert text.lstrip(chr(0xFEFF)) == "hello"
        assert enc == "utf-16"

    def test_utf16_not_tried_without_bom(self):
        """Regression: UTF-16 decodes any even-length byte string, so
        trying it blind turned cp1252 bytes into CJK garbage."""
        text, enc, _ = _decode(bytes([0x93]) + b"quoted" + bytes([0x94]))
        assert enc != "utf-16"
        assert "quoted" in text

    def test_cp1252_smart_quotes(self):
        text, enc, _ = _decode(bytes([0x93]) + b"quoted" + bytes([0x94]))
        assert "quoted" in text
        assert enc in ("cp1252", "latin-1")

    def test_undecodable_never_raises(self):
        text, enc, _ = _decode(bytes([0xFF, 0xFE, 0x00, 0x81]) + b"valid")
        assert isinstance(text, str)
        assert enc


class TestExtractPlainText:
    def setup_method(self):
        self.parser = TextParser.__new__(TextParser)

    def test_paragraphs_split_on_blank_lines(self):
        els = self.parser._extract("First para.\n\nSecond para.", is_markdown=False)
        assert [e.element_type for e in els] == ["paragraph", "paragraph"]
        assert els[0].text == "First para."
        assert els[1].text == "Second para."

    def test_multiline_paragraph_stays_together(self):
        els = self.parser._extract("line one\nline two\n\nnext", is_markdown=False)
        assert els[0].text == "line one\nline two"
        assert els[0].metadata["lines"] == 2

    def test_markdown_syntax_ignored_when_not_markdown(self):
        els = self.parser._extract("# Not a header", is_markdown=False)
        assert els[0].element_type == "paragraph"

    def test_empty_input_yields_nothing(self):
        assert self.parser._extract("", is_markdown=False) == []

    def test_whitespace_only_yields_nothing(self):
        assert self.parser._extract("\n\n   \n\n", is_markdown=False) == []


class TestExtractMarkdown:
    def setup_method(self):
        self.parser = TextParser.__new__(TextParser)

    def test_atx_headers_with_levels(self):
        els = self.parser._extract("# H1\n\n## H2\n\n###### H6", is_markdown=True)
        assert [e.element_type for e in els] == ["header"] * 3
        assert [e.metadata["level"] for e in els] == [1, 2, 6]
        assert [e.text for e in els] == ["H1", "H2", "H6"]

    def test_atx_closing_hashes_stripped(self):
        els = self.parser._extract("## Title ##", is_markdown=True)
        assert els[0].text == "Title"

    def test_seven_hashes_is_not_a_header(self):
        els = self.parser._extract("####### too many", is_markdown=True)
        assert els[0].element_type == "paragraph"

    def test_setext_headers(self):
        els = self.parser._extract("Title\n=====\n\nSub\n---", is_markdown=True)
        headers = [e for e in els if e.element_type == "header"]
        assert [h.text for h in headers] == ["Title", "Sub"]
        assert [h.metadata["level"] for h in headers] == [1, 2]

    def test_fenced_code_block(self):
        md = "intro\n\n```python\nx = 1\ny = 2\n```\n\nafter"
        els = self.parser._extract(md, is_markdown=True)
        code = next(e for e in els if e.element_type == "code")
        assert code.text == "x = 1\ny = 2"

    def test_markdown_inside_fence_is_not_a_header(self):
        els = self.parser._extract("```\n# not a header\n```", is_markdown=True)
        assert all(e.element_type != "header" for e in els)

    def test_tilde_fence(self):
        els = self.parser._extract("~~~\ncode here\n~~~", is_markdown=True)
        assert any(e.element_type == "code" for e in els)

    def test_unterminated_fence_degrades_to_paragraph(self):
        els = self.parser._extract("```\ndangling", is_markdown=True)
        assert els, "content must not be silently dropped"
        assert els[0].text == "dangling"

    def test_positions_are_sequential(self):
        els = self.parser._extract("# A\n\ntext\n\n## B", is_markdown=True)
        assert [e.position for e in els] == list(range(len(els)))
