"""Typed request/response models for the renderer."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

from .errors import ValidationError

Orientation = Literal["portrait", "landscape"]


@dataclass(slots=True)
class Margins:
    """Page margins expressed as CSS-size strings (for example, '10mm')."""

    top: str = "0mm"
    right: str = "0mm"
    bottom: str = "0mm"
    left: str = "0mm"

    @classmethod
    def from_payload(cls, payload: dict[str, Any] | None) -> Margins:
        """Build margins from input payload, defaulting missing values to 0mm."""
        if payload is None:
            return cls()
        return cls(
            top=str(payload.get("top", "0mm")),
            right=str(payload.get("right", "0mm")),
            bottom=str(payload.get("bottom", "0mm")),
            left=str(payload.get("left", "0mm")),
        )


@dataclass(slots=True)
class PaperSize:
    """Custom paper size dimensions (for example, width='210mm', height='297mm')."""

    width: str
    height: str

    @classmethod
    def from_payload(cls, payload: dict[str, Any] | None) -> PaperSize | None:
        """Build paper size from input payload, raising if missing width or height."""
        if payload is None:
            return None
        width = payload.get("width")
        height = payload.get("height")
        if not width or not height:
            raise ValidationError("paper_size must contain both width and height")
        return cls(width=str(width), height=str(height))


@dataclass(slots=True)
class RenderRequest:
    """Normalized PDF render request used by all adapters."""

    html: str
    format: str | None = "a4"
    paper_size: PaperSize | None = None
    margins: Margins = field(default_factory=Margins)
    orientation: Orientation = "portrait"
    header_html: str | None = None
    footer_html: str | None = None
    print_background: bool = True
    prefer_css_page_size: bool = False
    timeout_ms: int = 30_000
    filename: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> RenderRequest:
        """Build render request from payload.

        Raise if html is missing or orientation is invalid.
        """
        html = str(payload.get("html", "")).strip()
        if not html:
            raise ValidationError("html is required")

        orientation_raw = str(payload.get("orientation", "portrait")).lower()
        if orientation_raw not in {"portrait", "landscape"}:
            raise ValidationError("orientation must be 'portrait' or 'landscape'")
        orientation: Orientation = (
            "landscape" if orientation_raw == "landscape" else "portrait"
        )

        request = cls(
            html=html,
            format=(str(payload["format"]).lower() if payload.get("format") else None),
            paper_size=PaperSize.from_payload(payload.get("paper_size")),
            margins=Margins.from_payload(payload.get("margins")),
            orientation=orientation,
            header_html=payload.get("header_html"),
            footer_html=payload.get("footer_html"),
            print_background=bool(payload.get("print_background", True)),
            prefer_css_page_size=bool(payload.get("prefer_css_page_size", False)),
            timeout_ms=int(payload.get("timeout_ms", 30_000)),
            filename=payload.get("filename"),
            metadata=_string_dict(payload.get("metadata")),
        )
        request.validate()
        return request

    def validate(self) -> None:
        """Validate the render request, raising if invalid."""
        if self.format and self.paper_size:
            raise ValidationError("format and paper_size are mutually exclusive")
        if self.timeout_ms < 1 or self.timeout_ms > 120_000:
            raise ValidationError("timeout_ms must be between 1 and 120000")
        if len(self.html.encode("utf-8")) > 2_000_000:
            raise ValidationError("html payload is too large")


@dataclass(slots=True)
class RenderResult:
    """Result returned by the shared rendering core."""

    pdf_bytes: bytes
    content_type: str = "application/pdf"
    generated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    filename: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)


def _string_dict(value: Any) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValidationError("metadata must be a key/value object")
    return {str(k): str(v) for k, v in value.items()}
