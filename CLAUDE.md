# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
uv sync                              # Install dependencies
uv run playwright install chromium   # Install browser (required once)
uv run pytest                        # Run all tests
uv run pytest tests/test_foo.py      # Run a single test file
uv run pytest -k "test_name"         # Run a single test by name
uv run ruff check .                  # Lint
uv run ruff format .                 # Format
uv run ty check                      # Type check
```

CLI usage: `echo '{"html":"<h1>Hello</h1>"}' | uv run python main.py`

## Architecture

Framework-agnostic PDF renderer: HTML in, PDF bytes out via Playwright/Chromium. Designed to be called from Laravel (Spatie PDF driver) across multiple runtimes.

**Core layer** (`render_image/`):
- `contracts.py` — `RenderRequest` (input) and `RenderResult` (output) dataclasses with `from_payload()` factory for JSON deserialization and validation
- `service.py` — `render_pdf()` (sync) and `render_pdf_async()` (async) entrypoints. Uses `PlaywrightRenderer` by default; accepts any `Renderer` protocol implementation for testing
- `errors.py` — `RenderError` (runtime) and `ValidationError` (input) exceptions

**Adapter layer** (`render_image/adapters/`):
- `aws_lambda.py` — API Gateway proxy event handler, returns base64-encoded PDF response
- `container.py` — Reads JSON from stdin/file, writes JSON to stdout. Also exposes `handle_payload()` used by other adapters
- `cloudflare.py` — Thin wrapper over container adapter; unwraps optional `render_request` key from Worker payloads

All adapters funnel through the same `render_pdf()` call. The Cloudflare adapter delegates to container's `handle_payload()`.

## Key Constraints

- Python >=3.14, managed with `uv`
- `format` and `paper_size` are mutually exclusive on `RenderRequest`
- `render_pdf()` detects active event loops and raises if called inside one — use `render_pdf_async()` instead
- HTML payload max size: 2MB; timeout range: 1–120000ms
