# Low-Level Design (LLD)

## Purpose

This document drills into the **internal structure** of each component — data shapes, function signatures, state transitions, and inter-stage contracts. It is the most detailed level of design and is read alongside the source code.

## Data shapes (the contracts between stages)

### Ingestion event (S3 → EventBridge)

```json
{
  "version": "0",
  "id": "1e5527d7-bb36-4608-8e9b-1a2b3c4d5e6f",
  "detail-type": "Object Created",
  "source": "aws.s3",
  "account": "<ACCOUNT_ID>",
  "time": "2026-08-27T12:00:00Z",
  "region": "ap-south-1",
  "resources": [
    "arn:aws:s3:::datacurator-raw-dev/ingests/retailpulse/2026/08/27/products.pdf"
  ],
  "detail": {
    "bucket": { "name": "datacurator-raw-dev" },
    "object": { "key": "ingests/retailpulse/2026/08/27/products.pdf", "size": 12345 }
  }
}
```

### Stage 1: Detect output → Stage 2: Parse input

```python
class DetectResult(BaseModel):
    job_id: str               # UUID
    source_bucket: str
    source_key: str
    detected_format: Literal["pdf", "csv", "json", "html", "audio", "image", "video", "unknown"]
    detected_encoding: str    # e.g., "utf-8"
    magic_bytes_verified: bool
    detected_at: str          # ISO 8601
    size_bytes: int
```

### Stage 2: Parse output → Stage 3: Chunk input

```python
class ParsedDocument(BaseModel):
    job_id: str
    detected_format: str
    text_content: str
    structured_elements: list[StructuredElement]   # tables, images, headers
    page_count: int | None
    language: str | None
    parse_duration_ms: int
    parser_version: str       # e.g., "docling-2.0.0"
    warnings: list[str] = []

class StructuredElement(BaseModel):
    element_type: Literal["table", "image", "header", "code_block", "list"]
    text: str | None
    metadata: dict
    page: int | None
    position: int | None
```

### Stage 3: Chunk output → Stage 4: Redact input

```python
class Chunk(BaseModel):
    chunk_id: str             # UUID
    job_id: str
    document_id: str
    chunk_index: int          # 0..N
    text: str                 # 200-500 tokens typically
    token_count: int
    overlap_with_previous: int
    chunk_strategy: str       # e.g., "semantic-v1"
    metadata: dict            # source-specific
    embedding_model: str | None  # set in stage 6
```

### Stage 4: Redact output → Stage 5: Embed input

```python
class RedactedChunk(Chunk):
    redaction_count: int
    redaction_types: list[str]   # ["email", "phone", "aadhaar"]
    redaction_policy_version: str
    original_text_hash: str       # for verification
```

### Stage 5: Embed output → Stage 6: Classify input

```python
class EmbeddedChunk(RedactedChunk):
    embedding: list[float]        # 1024 dims
    embedding_model: str          # "amazon.titan-embed-text-v2:0"
    embedding_dim: int
    embedding_duration_ms: int
```

### Stage 6: Classify output → Stage 7: Route input

```python
class ClassifiedChunk(EmbeddedChunk):
    classification: Classification

class Classification(BaseModel):
    category: str                # e.g., "product-listing"
    tags: list[str]
    confidence: float
    classifier_version: str
    model_used: str              # "claude-sonnet-4.5" or "rule-based-v1"
```

### Final: Vector + metadata + raw

```python
# S3 Vectors entry
{
  "key": "<chunk_id>",
  "data": { "float32": [...] },
  "metadata": { "source": "...", "format": "...", "category": "..." }
}

# DynamoDB item (chunk-metadata table)
{
  "chunk_id": "uuid",
  "job_id": "uuid",
  "document_id": "uuid",
  "source_bucket": "...",
  "source_key": "...",
  "detected_format": "pdf",
  "classification": { "category": "...", "tags": [...] },
  "embedding_model": "amazon.titan-embed-text-v2:0",
  "token_count": 312,
  "redaction_count": 3,
  "created_at": "2026-08-27T12:00:00Z",
  "ttl": 1893456000   # 30 days from creation
}
```

## Lambda function structure

Each Lambda follows the same pattern:

```python
# src/parsers/pdf.py
from src.common import BaseLambda, JobContext, stage

@stage(name="parse-pdf", input=DetectResult, output=ParsedDocument)
class PdfParser(BaseLambda):
    """Parse a PDF using Docling."""
    
    def setup(self) -> None:
        import docling
        self._parser = docling.DocumentParser()
    
    def handle(self, ctx: JobContext, inp: DetectResult) -> ParsedDocument:
        obj = self.s3.get_object(Bucket=inp.source_bucket, Key=inp.source_key)
        doc = self._parser.parse(obj["Body"].read())
        return ParsedDocument(
            job_id=inp.job_id,
            detected_format=inp.detected_format,
            text_content=doc.text,
            structured_elements=doc.elements,
            page_count=doc.page_count,
            language=doc.detected_language,
            parse_duration_ms=int((time.time() - start) * 1000),
            parser_version=docling.__version__,
        )
```

The `@stage` decorator:

- Validates input/output against Pydantic models
- Writes structured logs to CloudWatch
- Emits custom metrics to CloudWatch (duration, memory, errors)
- Handles retries with exponential backoff
- Sets the next state in the Step Function

## Step Function state machine (full)

```json
{
  "Comment": "DataCurator ingestion pipeline",
  "StartAt": "Detect",
  "States": {
    "Detect": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:ap-south-1:ACCOUNT:function:datacurator-detect-dev",
      "Retry": [{
        "ErrorEquals": ["States.TaskFailed"],
        "IntervalSeconds": 1,
        "MaxAttempts": 3,
        "BackoffRate": 2.0
      }],
      "Catch": [{
        "ErrorEquals": ["States.ALL"],
        "Next": "Failed"
      }],
      "Next": "Parse"
    },
    "Parse": { "Type": "Choice", "Choices": [
      { "Variable": "$.detected_format", "StringEquals": "pdf", "Next": "ParsePdf" },
      { "Variable": "$.detected_format", "StringEquals": "csv", "Next": "ParseCsv" },
      { "Variable": "$.detected_format", "StringEquals": "json", "Next": "ParseJson" }
    ], "Default": "Failed" },
    "ParsePdf": { "Type": "Task", "Resource": "...", "Next": "Chunk" },
    "ParseCsv": { "Type": "Task", "Resource": "...", "Next": "Chunk" },
    "ParseJson": { "Type": "Task", "Resource": "...", "Next": "Chunk" },
    "Chunk": { "Type": "Task", "Resource": "...", "Next": "Redact" },
    "Redact": { "Type": "Task", "Resource": "...", "Next": "Embed" },
    "Embed": { "Type": "Task", "Resource": "...", "Next": "Classify" },
    "Classify": { "Type": "Task", "Resource": "...", "Next": "Route" },
    "Route": { "Type": "Task", "Resource": "...", "End": true },
    "Failed": { "Type": "Fail", "Cause": "Pipeline failed" }
  }
}
```

## Chunking strategy details

**Default chunker** (`config/chunkers/default.yaml`):

- Target: 300 tokens per chunk
- Min: 100 tokens
- Max: 500 tokens
- Overlap: 50 tokens
- Splitter: recursive character text splitter
- Boundaries: respect sentence and paragraph boundaries

**Code chunker** (`config/chunkers/code.yaml`):

- Target: 400 tokens
- Splitter: language-aware (tree-sitter)
- Boundaries: function/class boundaries

**Legal chunker** (`config/chunkers/legal.yaml`):

- Target: 500 tokens
- Splitter: section/clause aware
- Preserves numbering

The chunker is selected by the `chunk_strategy` field, which is set by the parser based on the detected format and (optionally) the data source's `chunker` config.

## Embedding strategy details

- **Model**: `amazon.titan-embed-text-v2:0` (1024-dim)
- **Batch size**: 25 chunks per Bedrock API call
- **Concurrency**: up to 10 parallel invocations (Step Function Map state)
- **Retry**: 3 attempts, exponential backoff
- **Fallback**: if Titan v2 fails, classify-only and store without embedding (search degrades)

## Classification strategy

**Phase 1: rule-based + zero-shot**

- Categories defined in `config/classifier/categories.yaml`
- For each chunk, prompt the LLM with: "Given this chunk, which of these categories apply: [...]"
- Output: JSON `{"category": "...", "tags": [...], "confidence": 0.0-1.0}`

**Phase 3: self-learning**

- Weekly DSPy prompt optimization
- Inputs: chunks marked as "misclassified" in the KB UI
- Outputs: optimized prompt template
- CI: validate new prompt on held-out set; if better, auto-PR

## Search strategy (KB UI)

- **Embedding**: query embedded with same model (Titan v2)
- **Retrieval**: top-K=10 from S3 Vectors
- **Filtering**: post-filter by source/format/date in DynamoDB
- **Reranking** (optional Phase 3): cross-encoder rerank on top-50 then re-select top-10

## Failure isolation

Each stage's failure is contained:

- **Detect fails** → entire job fails; user can re-upload
- **Parse fails** → job fails with `parse_error`; logged in `jobs` table
- **Chunk fails** → job fails; original file untouched
- **Redact fails** → job fails; **no PII risk** because we never embed unredacted data
- **Embed fails** → 3 retries; if all fail, chunk stored without embedding (degrades search)
- **Classify fails** → chunk stored with `classification: null`; user can manually classify
- **Route fails** → 3 retries; if all fail, entire job fails; partial state cleaned up by Step Function

## See also

- [HLD](01-hld.md) — Service boundaries, deployment topology
- [Component diagram](03-component-diagram.md) — Module dependencies
- [Data flow](04-data-flow.md) — Sequence diagrams
