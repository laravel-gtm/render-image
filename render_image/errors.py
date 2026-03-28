"""Domain errors for PDF rendering."""


class RenderError(Exception):
    """Base class for rendering failures."""


class ValidationError(RenderError):
    """Raised when a render request is invalid."""
