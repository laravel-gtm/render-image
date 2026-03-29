"""Core rendering service using Playwright Chromium."""

from __future__ import annotations

import asyncio
import os
from typing import Protocol

from playwright.async_api import Page, PdfMargins, async_playwright

from .contracts import RenderRequest, RenderResult
from .errors import RenderError

_LAMBDA_CHROMIUM_ARGS = (
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--no-sandbox",
    "--no-zygote",
    "--single-process",
)


_FORMAT_MAP = {
    "a0": "A0",
    "a1": "A1",
    "a2": "A2",
    "a3": "A3",
    "a4": "A4",
    "a5": "A5",
    "a6": "A6",
    "legal": "Legal",
    "letter": "Letter",
    "tabloid": "Tabloid",
    "ledger": "Ledger",
}


class Renderer(Protocol):
    """Abstraction over rendering engines."""

    async def render(self, request: RenderRequest) -> RenderResult:
        """Render a PDF for the provided request."""
        ...


class PlaywrightRenderer:
    """Playwright-backed implementation for modern HTML/CSS rendering."""

    async def render(self, request: RenderRequest) -> RenderResult:
        """Render a single PDF request via a transient Chromium session."""
        request.validate()
        try:
            async with async_playwright() as playwright:
                if os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
                    browser = await playwright.chromium.launch(
                        args=list(_LAMBDA_CHROMIUM_ARGS),
                    )
                else:
                    browser = await playwright.chromium.launch()
                page = await browser.new_page()
                await page.set_content(request.html, wait_until="networkidle")

                pdf_bytes = await _render_page_pdf(page=page, request=request)
                await browser.close()
        except Exception as exc:  # pragma: no cover - external runtime errors
            raise RenderError(f"Failed to generate PDF: {exc}") from exc

        return RenderResult(
            pdf_bytes=pdf_bytes,
            filename=request.filename,
            metadata=request.metadata,
        )


async def render_pdf_async(
    request: RenderRequest, renderer: Renderer | None = None
) -> RenderResult:
    """Async rendering entrypoint for adapters that already run event loops."""

    active_renderer = renderer or PlaywrightRenderer()
    return await active_renderer.render(request)


def render_pdf(
    request: RenderRequest, renderer: Renderer | None = None
) -> RenderResult:
    """Synchronous rendering entrypoint for Lambda/CLI usage."""

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(render_pdf_async(request=request, renderer=renderer))

    raise RenderError(
        "render_pdf() cannot run inside an active event loop. "
        "Use await render_pdf_async(...) instead."
    )


async def _render_page_pdf(page: Page, request: RenderRequest) -> bytes:
    margin = PdfMargins(
        top=request.margins.top,
        right=request.margins.right,
        bottom=request.margins.bottom,
        left=request.margins.left,
    )
    display_header_footer = bool(request.header_html or request.footer_html)

    if request.paper_size:
        return await page.pdf(
            width=request.paper_size.width,
            height=request.paper_size.height,
            landscape=request.orientation == "landscape",
            margin=margin,
            print_background=request.print_background,
            prefer_css_page_size=request.prefer_css_page_size,
            display_header_footer=display_header_footer,
            header_template=request.header_html or "",
            footer_template=request.footer_html or "",
        )

    normalized_format: str | None = None
    if request.format:
        normalized_format = _FORMAT_MAP.get(request.format.lower())
        if not normalized_format:
            supported = ", ".join(sorted(_FORMAT_MAP.keys()))
            raise RenderError(
                f"Unsupported format '{request.format}'. Use one of: {supported}"
            )

    return await page.pdf(
        format=normalized_format,
        landscape=request.orientation == "landscape",
        margin=margin,
        print_background=request.print_background,
        prefer_css_page_size=request.prefer_css_page_size,
        display_header_footer=display_header_footer,
        header_template=request.header_html or "",
        footer_template=request.footer_html or "",
    )
