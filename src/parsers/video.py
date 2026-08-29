"""Video parser stub (Phase 2).

For Phase 1, video files are not processed.
Phase 2 will extract audio track and feed to audio parser.
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


@stage(name="parse-video", input_model=DataCuratorModel, output_model=ParsedDocument)
class VideoParser(BaseLambda):
    """Parse video via ffmpeg + Whisper (Phase 2). For now, returns a stub."""

    def setup(self) -> None:
        pass

    def handle(self, ctx: JobContext, inp: DataCuratorModel) -> ParsedDocument:
        raise ParseError(
            "Video parsing not yet implemented (Phase 2). "
            "Track issue: https://github.com/vijaymadhu/datacurator-meta/issues"
        )
