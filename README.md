# Render Image

Framework-agnostic Python PDF renderer designed to be called from Laravel via a
custom Spatie Laravel PDF driver, with one shared rendering core across:

- AWS Lambda + API Gateway
- Container service runtime
- Cloudflare Worker proxy flow

## What this implements

- A typed rendering contract (`RenderRequest`) that maps to common Spatie options:
  - `html`
  - `format` OR `paper_size`
  - `margins`
  - `orientation`
  - `header_html` / `footer_html`
- A shared Playwright/Chromium renderer:
  - `render_pdf(request)` (sync)
  - `render_pdf_async(request)` (async)
- Thin adapters:
  - `render_image.adapters.aws_lambda.lambda_handler`
  - `render_image.adapters.container.handle_payload`
  - `render_image.adapters.cloudflare.handle_worker_payload`

## Install

```bash
uv sync
uv run playwright install chromium
```

## Request contract

Minimal JSON payload:

```json
{
  "html": "<html><body><h1>Invoice</h1></body></html>"
}
```

Extended payload example:

```json
{
  "html": "<html><body><h1>Invoice #123</h1></body></html>",
  "format": "a4",
  "margins": { "top": "10mm", "right": "10mm", "bottom": "12mm", "left": "10mm" },
  "orientation": "portrait",
  "header_html": "<div style='font-size:10px;'>Header</div>",
  "footer_html": "<div style='font-size:10px;'>Footer</div>",
  "timeout_ms": 30000,
  "filename": "invoice-123.pdf",
  "metadata": { "invoice_id": "123" }
}
```

Notes:

- Use `format` (for example `a4`, `letter`) or `paper_size` (`width` and `height`), not both.
- Validation/auth should happen at API Gateway/edge service; this module still performs defensive validation.

## Runtime usage

### Container/CLI

```bash
echo '{"html":"<h1>Hello</h1>","format":"a4"}' | uv run python main.py
```

Outputs JSON that includes `pdf_base64`.

### AWS Lambda

Use handler:

```python
from render_image.adapters.aws_lambda import lambda_handler
```

Expected input: API Gateway proxy event with a JSON body.  
Output: API Gateway response with base64 encoded PDF body and `application/pdf`.

### Cloudflare Worker proxy flow

Workers should validate/authenticate and forward a JSON payload to your Python
origin. Keep the payload under `render_request` or send the request object as-is.

Python entrypoint:

```python
from render_image.adapters.cloudflare import handle_worker_payload
```
