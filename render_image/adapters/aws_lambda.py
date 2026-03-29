"""AWS Lambda adapter for API Gateway proxy payloads."""

from __future__ import annotations

import base64
import json
import os
import tomllib
from pathlib import Path
from typing import Any

from render_image.contracts import RenderRequest
from render_image.errors import RenderError, ValidationError
from render_image.service import render_pdf

_openapi_json: str | None = None


def lambda_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    """Handle API Gateway Lambda proxy events."""
    method = event.get("requestContext", {}).get("http", {}).get("method", "")
    path = event.get("rawPath", "")

    if method == "GET" and path == "/up":
        return _handle_health()
    if method == "GET" and path == "/openapi.json":
        return _handle_openapi()
    if method == "POST" and path == "/render":
        return _handle_render(event)

    return _json_error(404, f"Not found: {method} {path}")


def _handle_health() -> dict[str, Any]:
    task_root = Path(os.environ.get("LAMBDA_TASK_ROOT", "."))
    pyproject = task_root / "pyproject.toml"
    version = "unknown"
    if pyproject.is_file():
        with open(pyproject, "rb") as f:
            data = tomllib.load(f)
        version = data.get("project", {}).get("version", "unknown")

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(
            {
                "status": "ok",
                "service": "render-image",
                "version": version,
                "region": os.environ.get("AWS_REGION", "unknown"),
            }
        ),
    }


def _handle_openapi() -> dict[str, Any]:
    global _openapi_json  # noqa: PLW0603

    if _openapi_json is None:
        import yaml

        task_root = Path(os.environ.get("LAMBDA_TASK_ROOT", "."))
        spec_path = task_root / "openapi.yaml"
        with open(spec_path) as f:
            spec = yaml.safe_load(f)
        _openapi_json = json.dumps(spec)

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": _openapi_json,
    }


def _handle_render(event: dict[str, Any]) -> dict[str, Any]:
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
    return 'attachment; filename="document.pdf"'
