from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


# ── Outputs ───────────────────────────────────────────────────────────────────

@dataclass
class TextOutput:
    kind: Literal["text"] = "text"
    content: str = ""


@dataclass
class ImageOutput:
    kind: Literal["image"] = "image"
    path: str = ""      # relative from the post .md file
    index: int = 0


@dataclass
class ErrorOutput:
    kind: Literal["error"] = "error"
    name: str = ""
    value: str = ""


# ── Cells ─────────────────────────────────────────────────────────────────────

@dataclass
class MarkdownCell:
    kind: Literal["markdown"] = "markdown"
    content: str = ""


@dataclass
class CodeCell:
    kind: Literal["code"] = "code"
    source: str = ""
    language: str = "python"
    outputs: list = field(default_factory=list)  # list[TextOutput | ImageOutput | ErrorOutput]


@dataclass
class WidgetCell:
    """A cell whose output is interactive and cannot be rendered statically."""
    kind: Literal["widget"] = "widget"
    description: str = ""


@dataclass
class ExcerptMarker:
    """Sentinel injected by parsers to mark the <!-- more --> cut point."""
    kind: Literal["excerpt_marker"] = "excerpt_marker"


# ── Post ─────────────────────────────────────────────────────────────────────

@dataclass
class NotebookPost:
    meta: dict
    cells: list                    # list[MarkdownCell | CodeCell | WidgetCell | ExcerptMarker]
    nb_filename: str
    images: list[Path] = field(default_factory=list)
    asset_warnings: list[str] = field(default_factory=list)
