"""Common base classes, decorators, and types for DataCurator.

This module is the foundation for every Lambda handler. It provides:

- BaseLambda: abstract base class for all stage handlers
- JobContext: per-invocation context (job_id, source_bucket, etc.)
- @stage decorator: ties a handler to its input/output models and emits metrics
- DataCuratorModel: stdlib dataclass base (replaces pydantic.BaseModel)
- Structured logging via structlog
- Exception hierarchy

No external dependencies (no pydantic) — pure stdlib + boto3 + structlog.
"""

from __future__ import annotations

import functools
import time
import uuid
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from typing import Any, ClassVar, Literal, get_args, get_origin

import boto3
import structlog

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


# --- Dataclass base (pydantic-free) ---


def _strip_whitespace(value: Any) -> Any:
    """Recursively strip whitespace from strings in nested data."""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        return {k: _strip_whitespace(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_strip_whitespace(v) for v in value]
    if isinstance(value, tuple):
        return tuple(_strip_whitespace(v) for v in value)
    return value


def _check_literal(value: Any, annotation: Any) -> None:
    """Check that value matches a Literal type; raise TypeError if not."""
    if get_origin(annotation) is Literal:
        allowed = get_args(annotation)
        if value not in allowed:
            raise TypeError(
                f"Value {value!r} not in allowed Literal values: {allowed}"
            )


def _check_types(obj: Any) -> None:
    """Recursively type-check fields with Literal annotations."""
    if not is_dataclass(obj):
        return
    for f in fields(obj):
        if f.name.startswith("_"):
            continue
        value = getattr(obj, f.name)
        annotation = f.type
        # Resolve string annotations (from __future__ import annotations)
        if isinstance(annotation, str):
            # We use a small set, so just check by trying
            try:
                if annotation.startswith("Literal[") or annotation.startswith("typing.Literal["):
                    # Naive parse for "Literal['a', 'b']"
                    inner = annotation.split("Literal[")[1].rstrip("]")
                    allowed = tuple(s.strip().strip("'\"") for s in inner.split(","))
                    if value not in allowed:
                        raise TypeError(
                            f"Field {f.name}: {value!r} not in {allowed}"
                        )
            except (IndexError, ValueError):
                pass
        else:
            try:
                _check_literal(value, annotation)
            except TypeError as e:
                raise TypeError(f"Field {f.name}: {e}") from e
        # Recurse into nested dataclass
        if is_dataclass(value):
            _check_types(value)
        elif isinstance(value, list) and value and is_dataclass(value[0]):
            for item in value:
                _check_types(item)


@dataclass
class DataCuratorModel:
    """Base dataclass model.

    Provides pydantic-like ergonomics on top of stdlib dataclasses:
    - `from_dict(d)` classmethod: construct from a dict (replaces `Model(**d)`)
    - `to_dict()`: serialize to dict (replaces `model_dump()`)
    - Whitespace stripping on string fields
    - Literal type validation in __post_init__
    - Extra fields are ignored (lenient, for forward compat)
    """

    def __post_init__(self) -> None:
        # Strip whitespace from all string fields
        for f in fields(self):
            value = getattr(self, f.name)
            stripped = _strip_whitespace(value)
            if stripped is not value:
                object.__setattr__(self, f.name, stripped)
        # Validate Literal fields
        _check_types(self)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict (replaces pydantic.model_dump)."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DataCuratorModel":
        """Construct from a dict, ignoring unknown keys (replaces pydantic.model_validate).

        Performs nested construction for dataclass-typed fields.
        """
        if not isinstance(data, dict):
            raise TypeError(f"from_dict requires a dict, got {type(data).__name__}")
        known = {f.name for f in fields(cls)}
        kwargs: dict[str, Any] = {}
        for key, value in data.items():
            if key not in known:
                continue  # ignore extras
            # Recursively construct nested dataclasses
            f = next((fld for fld in fields(cls) if fld.name == key), None)
            if f is not None:
                annotation = f.type
                # Resolve string annotations
                if isinstance(annotation, str) and "." in annotation:
                    annotation = annotation.split(".")[-1]
                # Check if this is a nested dataclass field
                if isinstance(annotation, str):
                    ann_name = annotation
                else:
                    ann_name = getattr(annotation, "__name__", str(annotation))
                # Try to find a nested type
                nested = globals().get(ann_name) or _resolve_typing(annotation)
                if nested is not None and is_dataclass(nested) and isinstance(value, dict):
                    value = nested.from_dict(value)
                elif (
                    nested is not None
                    and is_dataclass(nested)
                    and isinstance(value, list)
                    and value
                    and isinstance(value[0], dict)
                ):
                    value = [nested.from_dict(v) for v in value]
            kwargs[key] = value
        return cls(**kwargs)


def _resolve_typing(annotation: Any) -> Any:
    """Resolve a typing annotation to its concrete class if possible."""
    # Handle Optional[X], List[X], etc.
    origin = get_origin(annotation)
    if origin is not None:
        args = get_args(annotation)
        for a in args:
            resolved = _resolve_typing(a)
            if resolved is not None and is_dataclass(resolved):
                return resolved
    # Handle string annotations
    if isinstance(annotation, str):
        return globals().get(annotation)
    # Handle direct class reference
    if isinstance(annotation, type):
        return annotation
    return None


# --- Inter-stage data models (dataclass-based) ---


@dataclass
class DetectResult(DataCuratorModel):
    """Output of the Detect stage, input to the Parse stage."""

    job_id: str
    source_bucket: str
    source_key: str
    detected_format: str
    detected_encoding: str = "utf-8"
    magic_bytes_verified: bool = True
    detected_at: str = ""
    size_bytes: int = 0


@dataclass
class StructuredElement(DataCuratorModel):
    """A structured element extracted by a parser (table, image, header)."""

    element_type: str  # "table" | "image" | "header" | "code_block" | "list" | "paragraph"
    text: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    page: int | None = None
    position: int | None = None


@dataclass
class ParsedDocument(DataCuratorModel):
    """Output of the Parse stage, input to the Chunk stage."""

    job_id: str
    detected_format: str
    text_content: str
    structured_elements: list[StructuredElement] = field(default_factory=list)
    page_count: int | None = None
    language: str | None = None
    parse_duration_ms: int = 0
    parser_version: str = ""
    warnings: list[str] = field(default_factory=list)


@dataclass
class Chunk(DataCuratorModel):
    """Output of the Chunk stage, input to the Redact stage."""

    chunk_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    job_id: str = ""
    document_id: str = ""
    chunk_index: int = 0
    text: str = ""
    token_count: int = 0
    overlap_with_previous: int = 0
    chunk_strategy: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    page: int | None = None
    embedding_model: str | None = None


@dataclass
class RedactedChunk(Chunk):
    """Output of the Redact stage, input to the Embed stage."""

    redaction_count: int = 0
    redaction_types: list[str] = field(default_factory=list)
    redaction_policy_version: str = ""
    original_text_hash: str = ""


@dataclass
class Classification(DataCuratorModel):
    """A classification label assigned to a chunk."""

    category: str = "general"
    tags: list[str] = field(default_factory=list)
    confidence: float = 0.0
    classifier_version: str = ""
    model_used: str = ""


@dataclass
class EmbeddedChunk(RedactedChunk):
    """Output of the Embed stage, input to the Classify stage."""

    embedding: list[float] = field(default_factory=list)
    embedding_model: str = ""
    embedding_dim: int = 0
    embedding_duration_ms: int = 0


@dataclass
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
                # Coerce input to expected model
                if input_model is not None and not isinstance(inp, input_model):
                    if isinstance(inp, dict):
                        inp = input_model.from_dict(inp)
                    else:
                        # Best-effort: dump and reconstruct
                        inp = input_model.from_dict(inp.to_dict() if hasattr(inp, "to_dict") else inp.__dict__)

                # Call the actual handler
                result = original_handle(self, ctx, inp)

                # Validate output
                if isinstance(result, list):
                    if output_model is not None:
                        result = [
                            r if isinstance(r, output_model)
                            else output_model.from_dict(r.to_dict() if hasattr(r, "to_dict") else r)
                            for r in result
                        ]
                elif output_model is not None and not isinstance(result, output_model):
                    result = output_model.from_dict(
                        result.to_dict() if hasattr(result, "to_dict") else result.__dict__
                    )

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
