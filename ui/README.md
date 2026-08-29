# DataCurator KB UI

Static, serverless, single-page web app for searching the DataCurator knowledge base and submitting feedback.

## Features

- **Search** — semantic search with query, top-K, source filter, format filter, min-score filter
- **Bulk feedback** — select multiple chunks and mark them all at once
- **Inline feedback** — per-result "Good / Misclassified / Misrouted" buttons
- **Live analytics** — searches today, avg duration, feedback submitted
- **Responsive** — works on desktop and mobile

## Architecture

```text
ui/
├── index.html      # Markup
├── style.css       # Styles (dark theme, GitHub-inspired)
└── app.js          # Client logic (vanilla JS, no build step)
```

The UI is intentionally **framework-free** to minimize bundle size and keep deployment simple. No React, no Vue, no build pipeline — just three files deployed to S3 + CloudFront.

## API integration

The UI calls the DataCurator API via `fetch()` with the API URL configured by:

1. **Build-time**: `window.DATACURATOR_API_URL` injected by Terraform into `index.html`
2. **Runtime**: read from `<meta name="api-url" content="...">` if present
3. **Dev fallback**: hardcoded `https://api.example.com`

For IAM-authenticated calls (production), the UI must use AWS SDK with SigV4 signing. For demo/dev, the API Gateway can be configured with no-auth, or a CloudFront proxy can add the auth header.

## Local development

```bash
# Serve locally
python -m http.server 8000 --directory ui
# Open http://localhost:8000

# For API testing, point at a local mock:
# Edit app.js config.apiUrl
```

## Deployment

The UI bucket (`datacurator-ui-dev`) is configured for static website hosting. CloudFront in front provides HTTPS.

```bash
# After terraform apply:
aws s3 sync ui/ s3://datacurator-ui-dev/static/ --delete

# CloudFront will pick up changes within 5 minutes (cache TTL)
# Or invalidate:
aws cloudfront create-invalidation --distribution-id <id> --paths "/static/*"
```

## Customization

- **Branding**: edit the `.brand h1` text in `index.html` and the colors in `style.css`
- **API URL**: edit `app.js` `config.apiUrl` or inject via Terraform
- **Categories**: edit the `category` tags rendered in `renderResults()`
