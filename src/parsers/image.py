"""Image parser stub (Phase 2).

For Phase 1, image files fall back to "unknown" format and are not processed.
Phase 2 will add ColPali-based visual embeddings.
"""

from __future__ import annotations

from src.common import (
    BaseLambda,
    DataCuratorModel,
    JobContext,
    ParsedDocument,
    ParseError,
    stage,
)


@stage(name="parse-image", input_model=DataCuratorModel, output_model=ParsedDocument)
class ImageParser(BaseLambda):
    """Parse image via ColPali (Phase 2). For now, returns a stub."""

    def setup(self) -> None:
        pass

    def handle(self, ctx: JobContext, inp: DataCuratorModel) -> ParsedDocument:
        # TODO(Phase 2): integrate ColPali
        raise ParseError(
            "Image parsing not yet implemented (Phase 2). "
            "Track issue: https://github.com/vijaymadhu/datacurator-meta/issues"
        )
