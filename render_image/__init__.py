"""Shared PDF rendering contracts and entrypoints."""

from .contracts import RenderRequest, RenderResult
from .service import render_pdf, render_pdf_async

__all__ = ["RenderRequest", "RenderResult", "render_pdf", "render_pdf_async"]
