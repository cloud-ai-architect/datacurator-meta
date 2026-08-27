# DataCurator Synthetic Data Generator

Generates a mixed-format test corpus (CSV, JSONL, Markdown, HTML, PDF) and uploads to your S3 raw bucket. Use this to:

- Smoke-test the end-to-end pipeline
- Provide demo data for the KB UI
- Power integration tests

## Usage

```bash
# Install dependencies
pip install boto3

# Run with defaults
python data-curator/generate.py

# Custom bucket / source
python data-curator/generate.py \
  --bucket datacurator-raw-dev \
  --source demo \
  --region ap-south-1
```

## What it generates

| File | Format | Rows | Notes |
|---|---|---|---|
| `products.csv` | CSV | 100 | Retail products (SKU, price, stock) |
| `orders.jsonl` | JSONL | 50 | Order records (one per line) |
| `returns-policy.md` | Markdown | — | Synthetic returns/refunds policy |
| `faq.html` | HTML | — | Customer FAQ with 5 Q&A |
| `catalog.pdf` | PDF | — | Placeholder product catalog |
| `customer-profile.json` | JSON | 1 | Sample customer record |

All files are uploaded to `s3://<bucket>/ingests/<source>/<YYYY>/<MM>/<DD>/`.

## Reproducibility

Uses a fixed random seed (default 42) so the same corpus is generated every time. Pass `--seed` to change.

## After generation

The pipeline will automatically trigger (via S3 → EventBridge → Step Function). To watch:

```bash
aws logs tail /aws/vendedlogs/states/datacurator-pipeline-dev --follow --region ap-south-1
```

To query the results:

```bash
# Wait ~30 seconds for the pipeline to complete, then:
curl -H "Authorization: AWS4-HMAC-SHA256 ..." \
  "https://<api-url>/search?q=returns+policy&top_k=5"
```
