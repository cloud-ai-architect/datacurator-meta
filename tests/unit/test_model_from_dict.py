"""Unit tests for DataCuratorModel.from_dict nested construction."""

from __future__ import annotations

from src.common import (
    Classification,
    ClassifiedChunk,
    ParsedDocument,
    StructuredElement,
)


CHUNK = {
    "chunk_id": "c1",
    "job_id": "j1",
    "document_id": "d1",
    "chunk_index": 0,
    "text": "hello",
    "embedding": [0.1, 0.2],
    "classification": {"category": "clinical", "confidence": 0.9},
}


class TestNestedConstruction:
    def test_optional_dataclass_field_is_constructed(self):
        """Regression: Model(**event) left this a dict, so router raised
        "dict object has no attribute category" on every execution."""
        c = ClassifiedChunk.from_dict(CHUNK)
        assert isinstance(c.classification, Classification)
        assert c.classification.category == "clinical"

    def test_list_of_dataclasses_is_constructed(self):
        pd = ParsedDocument.from_dict({
            "job_id": "j1",
            "detected_format": "text",
            "text_content": "x",
            "structured_elements": [
                {"element_type": "header", "text": "H", "metadata": {}, "position": 0},
                {"element_type": "paragraph", "text": "P", "metadata": {}, "position": 1},
            ],
        })
        assert all(isinstance(e, StructuredElement) for e in pd.structured_elements)
        assert pd.structured_elements[0].element_type == "header"

    def test_none_optional_stays_none(self):
        data = dict(CHUNK)
        data["classification"] = None
        assert ClassifiedChunk.from_dict(data).classification is None

    def test_already_constructed_instance_passes_through(self):
        data = dict(CHUNK)
        data["classification"] = Classification(category="fin", confidence=0.5)
        c = ClassifiedChunk.from_dict(data)
        assert isinstance(c.classification, Classification)
        assert c.classification.category == "fin"

    def test_unknown_keys_ignored(self):
        data = dict(CHUNK)
        data["ExecutedVersion"] = "$LATEST"
        data["StatusCode"] = 200
        c = ClassifiedChunk.from_dict(data)
        assert c.chunk_id == "c1"

    def test_empty_list_stays_empty(self):
        pd = ParsedDocument.from_dict({
            "job_id": "j1", "detected_format": "text",
            "text_content": "x", "structured_elements": [],
        })
        assert pd.structured_elements == []

    def test_non_dict_input_raises(self):
        import pytest
        with pytest.raises(TypeError):
            ClassifiedChunk.from_dict(["not", "a", "dict"])

    def test_roundtrip_to_dict_from_dict(self):
        c = ClassifiedChunk.from_dict(CHUNK)
        again = ClassifiedChunk.from_dict(c.to_dict())
        assert isinstance(again.classification, Classification)
        assert again.classification.category == "clinical"
