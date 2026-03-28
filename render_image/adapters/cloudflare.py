"""Cloudflare Worker proxy payload adapter.

Workers cannot directly execute this Python module. Instead, a Worker should forward
validated payloads to a runtime that hosts this module (Lambda/container/etc.).
This adapter keeps request/response mapping consistent for that flow.
"""

from __future__ import annotations

from typing import Any

from render_image.adapters.container import handle_payload


def handle_worker_payload(worker_payload: dict[str, Any]) -> dict[str, Any]:
    """Handle payloads forwarded by a Cloudflare Worker."""

    payload = worker_payload.get("render_request", worker_payload)
    if not isinstance(payload, dict):
        raise ValueError("Cloudflare worker payload must be a JSON object")
    return handle_payload(payload)
