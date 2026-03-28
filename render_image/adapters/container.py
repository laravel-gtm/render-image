"""Container/runtime adapter for internal service invocation."""

from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path
from typing import Any

from render_image.contracts import RenderRequest
from render_image.service import render_pdf


def handle_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Convert a JSON payload into a normalized JSON response."""

    request = RenderRequest.from_payload(payload)
    result = render_pdf(request)
    return {
        "content_type": result.content_type,
        "filename": result.filename or "document.pdf",
        "pdf_base64": base64.b64encode(result.pdf_bytes).decode("ascii"),
        "metadata": result.metadata,
        "generated_at": result.generated_at,
    }


def main() -> int:
    """Read JSON payload from stdin or file and write JSON to stdout."""

    parser = argparse.ArgumentParser(description="Render PDF from a JSON payload.")
    parser.add_argument(
        "--input-json",
        help="Path to request JSON file. If omitted, reads JSON from stdin.",
    )
    args = parser.parse_args()

    if args.input_json:
        payload = json.loads(Path(args.input_json).read_text(encoding="utf-8"))
    else:
        payload = json.loads(sys.stdin.read())

    response = handle_payload(payload)
    sys.stdout.write(json.dumps(response))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
