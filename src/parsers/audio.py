"""Audio parser stub (Phase 2).

For Phase 1, audio files fall back to "unknown" format and are not processed.
Phase 2 will add Whisper-based transcription.
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


@stage(name="parse-audio", input_model=DataCuratorModel, output_model=ParsedDocument)
class AudioParser(BaseLambda):
    """Parse audio via Whisper (Phase 2). For now, returns a stub."""

    def setup(self) -> None:
        pass

    def handle(self, ctx: JobContext, inp: DataCuratorModel) -> ParsedDocument:
        # TODO(Phase 2): integrate Whisper
        # - Upload audio to S3
        # - Call Whisper (via SageMaker async endpoint or local model)
        # - Return transcript
        raise ParseError(
            "Audio parsing not yet implemented (Phase 2). "
            "Track issue: https://github.com/vijaymadhu/datacurator-meta/issues"
        )
