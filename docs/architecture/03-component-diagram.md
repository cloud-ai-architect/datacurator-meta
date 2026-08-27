# Component Diagram

## Purpose

This document shows the **internal module structure** of DataCurator and how the Python source, Terraform, and policies are organized into modules. It complements the [HLD](01-hld.md) (which is service-oriented) by showing the **codebase** structure.

## Repository structure (code modules)

```mermaid
graph TB
    subgraph App[src/ - Python application]
        Common[common.py<br/>BaseLambda, JobContext, stage decorator]
        Detect[detect.py<br/>Format detection]
        Parsers[parsers/<br/>pdf.py, csv.py, json.py, ...]
        Chunker[chunker.py<br/>Semantic chunker]
        Redactor[redactor.py<br/>OPA wrapper]
        Embedder[embedder.py<br/>Bedrock wrapper]
        Classifier[classifier.py<br/>LangGraph]
        Router[router.py<br/>Fan-out to stores]
        Client[client.py<br/>Public API for downstream]
    end

    subgraph Config[config/ - YAML]
        Datasources[datasources/<br/>Per-source YAML]
        ParsersCfg[parsers/<br/>Per-format YAML]
        ChunkersCfg[chunkers/<br/>Per-strategy YAML]
        EmbeddersCfg[embedders/<br/>Per-model YAML]
    end

    subgraph Policies[policies/ - OPA Rego]
        PII[pii-redaction.rego]
        PIITests[pii-redaction_test.rego]
        Retention[retention.rego]
    end

    subgraph Prompts[prompts/ - LLM templates]
        ClassifierPrompt[classifier.yaml]
    end

    subgraph Infra[infra/terraform/ - IaC]
        Modules[modules/<br/>raw-bucket, vectors-bucket, ...]
        Envs[envs/<br/>dev.tfvars, staging.tfvars, prod.tfvars]
    end

    subgraph UI[ui/ - Static KB UI]
        IndexHTML[index.html]
        AppJS[app.js]
        StylesCSS[style.css]
    end

    subgraph Scripts[scripts/]
        Bootstrap[bootstrap.sh]
        Destroy[destroy.sh]
    end

    subgraph DataCurator[data-curator/]
        Generator[generate.py<br/>Synthetic data]
    end

    subgraph Tests[tests/]
        Unit[unit/]
        Integration[integration/]
        Fixtures[fixtures/]
    end

    Detect --> Common
    Parsers --> Common
    Chunker --> Common
    Redactor --> Common
    Redactor --> Policies
    Embedder --> Common
    Classifier --> Common
    Classifier --> Prompts
    Router --> Common
    Client --> Common

    Parsers --> Config
    Chunker --> Config
    Embedder --> Config
    Classifier --> Config
```

## Python module dependency graph

```mermaid
graph TB
    common[common.py]
    detect[detect.py]
    parsers[parsers/*.py]
    chunker[chunker.py]
    redactor[redactor.py]
    embedder[embedder.py]
    classifier[classifier.py]
    router[router.py]
    client[client.py]
    lambdas[lambdas/ - one file per stage]

    detect --> common
    parsers --> common
    parsers --> config[config parsers/*.yaml]
    chunker --> common
    chunker --> config
    redactor --> common
    redactor --> policies[OPA Rego]
    embedder --> common
    embedder --> config
    classifier --> common
    classifier --> prompts[prompts/*.yaml]
    router --> common
    client --> common

    lambdas --> detect
    lambdas --> parsers
    lambdas --> chunker
    lambdas --> redactor
    lambdas --> embedder
    lambdas --> classifier
    lambdas --> router
```

## Terraform module dependency graph

```mermaid
graph TB
    main[main.tf]
    rawBucket[modules/raw-bucket]
    vectorsBucket[modules/vectors-bucket]
    uiBucket[modules/ui-bucket]
    dynamodb[modules/dynamodb]
    lambdas[modules/lambdas]
    stepFunction[modules/step-function]
    eventbridge[modules/eventbridge]
    apigw[modules/apigateway]
    cloudfront[modules/cloudfront]
    iam[modules/iam]
    resourceGroup[modules/resource-group]
    oidc[modules/oidc]

    main --> rawBucket
    main --> vectorsBucket
    main --> uiBucket
    main --> dynamodb
    main --> lambdas
    main --> stepFunction
    main --> eventbridge
    main --> apigw
    main --> cloudfront
    main --> iam
    main --> resourceGroup

    rawBucket --> iam
    vectorsBucket --> iam
    uiBucket --> iam
    dynamodb --> iam
    lambdas --> iam
    stepFunction --> iam
    apigw --> iam
    cloudfront --> uiBucket

    eventBridge --> stepFunction
    eventBridge --> rawBucket
    apigw --> lambdas

    iam --> oidc
```

## Data flow at the component level

```mermaid
sequenceDiagram
    participant S3 as S3 raw bucket
    participant EB as EventBridge
    participant SF as Step Function
    participant D as detect-lambda
    participant P as parse-lambda
    participant C as chunk-lambda
    participant R as redact-lambda
    participant E as embed-lambda
    participant CLS as classify-lambda
    participant RT as route-lambda
    participant VEC as S3 Vectors
    participant DDB as DynamoDB
    participant BR as Bedrock
    participant OPA as OPA (in-process)

    S3->>EB: s3:ObjectCreated
    EB->>SF: StartExecution
    SF->>D: detect(state)
    D-->>SF: DetectResult
    SF->>P: parse(state)
    P-->>SF: ParsedDocument
    SF->>C: chunk(state)
    C-->>SF: list[Chunk]
    SF->>R: redact(state)
    R->>OPA: evaluate(pii-redaction, text)
    OPA-->>R: redacted_text
    R-->>SF: list[RedactedChunk]
    SF->>E: embed(state)
    E->>BR: InvokeModel(titan-embed-v2, texts)
    BR-->>E: list[vector]
    E-->>SF: list[EmbeddedChunk]
    SF->>CLS: classify(state)
    CLS-->>SF: list[ClassifiedChunk]
    SF->>RT: route(state)
    RT->>VEC: PutVectors
    RT->>DDB: BatchWriteItem
    RT-->>SF: success
```

## Configuration files

Each YAML config is **typed** and **validated** at Lambda startup. A missing field or wrong type fails the Lambda fast.

| Config | Validated by | Used by |
|---|---|---|
| `config/datasources/*.yaml` | Pydantic | Parser, Router |
| `config/parsers/*.yaml` | Pydantic | Parsers |
| `config/chunkers/*.yaml` | Pydantic | Chunker |
| `config/embedders/*.yaml` | Pydantic | Embedder |
| `prompts/*.yaml` | Pydantic | Classifier |
| `policies/*.rego` | OPA test | Redactor |

## OPA policy structure

```mermaid
graph TB
    subgraph OPA[OPA bundle]
        PII[datacurator.pii<br/>pii-redaction.rego]
        PIIRedact[redact function]
        PIITest[pii-redaction_test.rego]
        Retention[datacurator.retention<br/>retention.rego]
    end

    Redactor[redactor.py] -->|in-process| PII
    PII --> PIIRedact
    PIITest -->|opa test| PII
```

The OPA bundle is **embedded** in the Lambda deployment package (not loaded from S3 at runtime), so there's no runtime dependency on S3 for policy evaluation.

## Where each component lives

```
datacurator-meta/
├── src/                          # Python application code
│   ├── common.py                 # BaseLambda, JobContext, stage decorator
│   ├── detect.py                 # Format auto-detection
│   ├── parsers/                  # Per-format parsers
│   │   ├── __init__.py
│   │   ├── pdf.py
│   │   ├── csv.py
│   │   ├── json.py
│   │   ├── html.py
│   │   ├── audio.py              # Phase 2
│   │   ├── image.py              # Phase 2
│   │   └── video.py              # Phase 2
│   ├── chunker.py                # Semantic chunking
│   ├── redactor.py               # OPA wrapper
│   ├── embedder.py               # Bedrock wrapper
│   ├── classifier.py             # LangGraph classifier
│   ├── router.py                 # Fan-out to stores
│   ├── client.py                 # Public API for downstream projects
│   ├── lambdas/                  # Lambda entry points
│   │   ├── detect_handler.py
│   │   ├── parse_handler.py
│   │   ├── chunk_handler.py
│   │   ├── redact_handler.py
│   │   ├── embed_handler.py
│   │   ├── classify_handler.py
│   │   ├── route_handler.py
│   │   ├── search_handler.py
│   │   └── feedback_handler.py
│   └── lambdas_layer/            # Shared layer (Pydantic, OPA, boto3)
│       └── python/
├── policies/                     # OPA Rego
│   ├── pii-redaction.rego
│   ├── pii-redaction_test.rego
│   ├── retention.rego
│   └── retention_test.rego
├── prompts/                      # LLM prompt templates
│   └── classifier.yaml
├── config/                       # YAML configurations
│   ├── datasources/
│   ├── parsers/
│   ├── chunkers/
│   └── embedders/
├── infra/terraform/              # IaC
│   ├── main.tf
│   ├── variables.tf
│   ├── providers.tf
│   ├── data.tf
│   ├── locals.tf
│   ├── modules/
│   │   ├── raw-bucket/
│   │   ├── vectors-bucket/
│   │   ├── ui-bucket/
│   │   ├── dynamodb/
│   │   ├── lambdas/
│   │   ├── step-function/
│   │   ├── eventbridge/
│   │   ├── apigateway/
│   │   ├── cloudfront/
│   │   ├── iam/
│   │   ├── oidc/
│   │   └── resource-group/
│   └── envs/
│       ├── dev.tfvars
│       ├── staging.tfvars
│       └── prod.tfvars
├── ui/                           # Static KB UI
│   ├── index.html
│   ├── app.js
│   ├── style.css
│   └── README.md
├── scripts/                      # Operational scripts
│   ├── bootstrap.sh              # One-time setup for a new AWS account
│   ├── destroy.sh                # Tear down
│   └── verify.sh                 # Health check
├── data-curator/                 # Synthetic data generator
│   └── generate.py
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
└── docs/                         # Documentation
    ├── architecture/
    ├── adr/
    ├── runbooks/
    └── api/
```

## See also

- [HLD](01-hld.md) — Service boundaries
- [LLD](02-lld.md) — Data shapes and code structure
- [Data flow](04-data-flow.md) — Sequence diagrams
