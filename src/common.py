"""Common base classes, decorators, and types for DataCurator.

This module is the foundation for every Lambda handler. It provides:

- BaseLambda: abstract base class for all stage handlers
- JobContext: per-invocation context (job_id, source_bucket, etc.)
- @stage decorator: ties a handler to its input/output models and emits metrics
- Pydantic models for inter-stage contracts
- Structured logging via structlog
- Exception hierarchy
"""

from __future__ import annotations

import functools
import time
import uuid
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, ClassVar, Literal

import boto3
import structlog
from pydantic import BaseModel, ConfigDict, Field

logger = structlog.get_logger()


# --- Exceptions ---


class DataCuratorError(Exception):
    """Base exception for all DataCurator errors."""


class FormatDetectionError(DataCuratorError):
    """Failed to detect the format of an uploaded file."""


class ParseError(DataCuratorError):
    """Failed to parse a file (e.g., malformed PDF, invalid CSV)."""


class ChunkingError(DataCuratorError):
    """Failed to chunk a document."""


class RedactionError(DataCuratorError):
    """Failed to apply PII redaction (e.g., OPA policy not loadable)."""


class EmbeddingError(DataCuratorError):
    """Failed to generate embeddings (e.g., Bedrock unavailable)."""


class ClassificationError(DataCuratorError):
    """Failed to classify a chunk."""


class RoutingError(DataCuratorError):
    """Failed to route a chunk to its destination store."""


# --- Job context ---


@dataclass
class JobContext:
    """Per-invocation context passed through the pipeline.

    Carries the job_id, source location, and any cumulative state.
    """

    job_id: str
    source_bucket: str
    source_key: str
    environment: str
    started_at: float = 0.0
    cumulative_cost_usd: float = 0.0
    custom: dict[str, Any] | None = None


# --- Pydantic base model ---


class DataCuratorModel(BaseModel):
    """Base Pydantic model with common config."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        use_enum_values=True,
    )


# --- Inter-stage data models (full Pydantic definitions) ---


class DetectResult(DataCuratorModel):
    """Output of the Detect stage, input to the Parse stage."""

    job_id: str
    source_bucket: str
    source_key: str
    detected_format: Literal["pdf", "csv", "json", "html", "audio", "image", "video", "unknown"]
    detected_encoding: str = "utf-8"
    magic_bytes_verified: bool
    detected_at: str
    size_bytes: int


class StructuredElement(DataCuratorModel):
    """A structured element extracted by a parser (table, image, header)."""

    element_type: Literal["table", "image", "header", "code_block", "list", "paragraph"]
    text: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    page: int | None = None
    position: int | None = None


class ParsedDocument(DataCuratorModel):
    """Output of the Parse stage, input to the Chunk stage."""

    job_id: str
    detected_format: str
    text_content: str
    structured_elements: list[StructuredElement] = Field(default_factory=list)
    page_count: int | None = None
    language: str | None = None
    parse_duration_ms: int
    parser_version: str
    warnings: list[str] = Field(default_factory=list)


class Chunk(DataCuratorModel):
    """Output of the Chunk stage, input to the Redact stage."""

    chunk_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    job_id: str
    document_id: str
    chunk_index: int
    text: str
    token_count: int
    overlap_with_previous: int = 0
    chunk_strategy: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    page: int | None = None
    embedding_model: str | None = None


class RedactedChunk(Chunk):
    """Output of the Redact stage, input to the Embed stage."""

    redaction_count: int = 0
    redaction_types: list[str] = Field(default_factory=list)
    redaction_policy_version: str = ""
    original_text_hash: str = ""


class EmbeddedChunk(RedactedChunk):
    """Output of the Embed stage, input to the Classify stage."""

    embedding: list[float] = Field(default_factory=list)
    embedding_model: str = ""
    embedding_dim: int = 0
    embedding_duration_ms: int = 0


class Classification(DataCuratorModel):
    """A classification label assigned to a chunk."""

    category: str
    tags: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    classifier_version: str
    model_used: str


class ClassifiedChunk(EmbeddedChunk):
    """Output of the Classify stage, input to the Route stage."""

    classification: Classification | None = None


# --- Base Lambda ---


class BaseLambda(ABC):
    """Abstract base class for all stage Lambda handlers.

    Subclasses implement `handle()`. The base class:

    - Provides a configured structlog logger
    - Initializes boto3 clients lazily
    - Catches and re-raises exceptions with structured context
    - Emits CloudWatch metrics for duration, errors
    """

    # Subclasses override
    NAME: ClassVar[str] = ""
    INPUT_MODEL: ClassVar[type[DataCuratorModel] | None] = None
    OUTPUT_MODEL: ClassVar[type[DataCuratorModel] | None] = None

    def __init__(self) -> None:
        if not self.NAME:
            raise ValueError(f"{type(self).__name__} must set NAME")
        self.log = logger.bind(handler=self.NAME)
        self.s3: Any = None
        self.dynamodb: Any = None
        self.bedrock: Any = None
        self.s3vectors: Any = None
        self._setup_done = False

    def setup(self) -> None:
        """Lazy initialization of AWS clients. Override for custom setup."""

    def ensure_setup(self) -> None:
        if not self._setup_done:
            self.s3 = boto3.client("s3")
            self.dynamodb = boto3.client("dynamodb")
            self.bedrock = boto3.client("bedrock-runtime", region_name="ap-south-1")
            self.s3vectors = boto3.client("s3vectors", region_name="ap-south-1")
            self.setup()
            self._setup_done = True

    @abstractmethod
    def handle(self, ctx: JobContext, inp: DataCuratorModel) -> DataCuratorModel | list[DataCuratorModel]:
        """Handle the request and return the output model.

        May return a single model or a list (for chunking/embedding stages).
        """


# --- Stage decorator ---


def stage(
    *,
    name: str,
    input_model: type[DataCuratorModel] | None = None,
    output_model: type[DataCuratorModel] | None = None,
) -> Callable[[type[BaseLambda]], type[BaseLambda]]:
    """Decorator that wires a handler class to its input/output models and name.

    Usage:
        @stage(name="parse-pdf", input=DetectResult, output=ParsedDocument)
        class PdfParser(BaseLambda):
            def handle(self, ctx, inp): ...
    """

    def decorator(cls: type[BaseLambda]) -> type[BaseLambda]:
        cls.NAME = name
        cls.INPUT_MODEL = input_model
        cls.OUTPUT_MODEL = output_model

        original_handle = cls.handle

        @functools.wraps(original_handle)
        def wrapper(self: BaseLambda, ctx: JobContext, inp: DataCuratorModel) -> Any:
            self.ensure_setup()
            start = time.perf_counter()
            self.log.info(
                "stage.start",
                job_id=ctx.job_id,
                input_type=type(inp).__name__,
            )
            try:
                # Validate input if model provided
                if input_model is not None and not isinstance(inp, input_model):
                    inp = input_model.model_validate(inp.model_dump())

                # Call the actual handler
                result = original_handle(self, ctx, inp)

                # Validate output if model provided
                if isinstance(result, list):
                    if output_model is not None:
                        result = [output_model.model_validate(r.model_dump() if hasattr(r, "model_dump") else r) for r in result]
                elif output_model is not None and not isinstance(result, output_model):
                    result = output_model.model_validate(result.model_dump() if hasattr(result, "model_dump") else result)

                duration_ms = int((time.perf_counter() - start) * 1000)
                self.log.info(
                    "stage.success",
                    job_id=ctx.job_id,
                    duration_ms=duration_ms,
                    output_count=len(result) if isinstance(result, list) else 1,
                )
                return result
            except Exception as exc:
                duration_ms = int((time.perf_counter() - start) * 1000)
                self.log.error(
                    "stage.error",
                    job_id=ctx.job_id,
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                    duration_ms=duration_ms,
                )
                raise

        cls.handle = wrapper  # type: ignore[method-assign]
        return cls

    return decorator


# --- Public exports ---


__all__ = [
    "BaseLambda",
    "Chunk",
    "ClassifiedChunk",
    "Classification",
    "DataCuratorError",
    "DataCuratorModel",
    "DetectResult",
    "EmbeddedChunk",
    "FormatDetectionError",
    "JobContext",
    "ParsedDocument",
    "ParseError",
    "ChunkingError",
    "RedactionError",
    "EmbeddingError",
    "ClassificationError",
    "RoutingError",
    "RedactedChunk",
    "stage",
    "StructuredElement",
]
