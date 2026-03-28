"""AWS Lambda adapter for API Gateway proxy payloads."""

from __future__ import annotations

import base64
import json
from typing import Any

from render_image.contracts import RenderRequest
from render_image.errors import RenderError, ValidationError
from render_image.service import render_pdf


def lambda_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    """Handle API Gateway Lambda proxy events."""

    try:
        payload = _extract_payload(event)
        request = RenderRequest.from_payload(payload)
        result = render_pdf(request)

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": result.content_type,
                "Content-Disposition": _content_disposition(result.filename),
            },
            "isBase64Encoded": True,
            "body": base64.b64encode(result.pdf_bytes).decode("ascii"),
        }
    except ValidationError as exc:
        return _json_error(400, str(exc))
    except RenderError as exc:
        return _json_error(502, str(exc))


def _extract_payload(event: dict[str, Any]) -> dict[str, Any]:
    raw_body = event.get("body")
    if raw_body is None:
        return {}
    if event.get("isBase64Encoded"):
        decoded = base64.b64decode(str(raw_body)).decode("utf-8")
        return json.loads(decoded)
    return json.loads(str(raw_body))


def _json_error(status_code: int, message: str) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"error": message}),
    }


def _content_disposition(filename: str | None) -> str:
    if filename:
        return f'attachment; filename="{filename}"'
    return "attachment; filename=\"document.pdf\""
