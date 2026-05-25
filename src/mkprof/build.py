"""
mkprof.build — Textual TUI for converting notebooks and running mkdocs.
"""

import asyncio
import datetime
import shutil
import time
import traceback
from datetime import date as date_type
from pathlib import Path

from rich.markup import escape as markup_escape

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Header, Input, Label, RichLog, SelectionList, Static, TextArea

from mkprof.config import MkprofConfig
from mkprof.notebook import render as render_nb
from mkprof.notebook.jupyter import (
    extract_metadata as extract_nb_metadata,
    parse as parse_nb,
    peek_hints as peek_nb_hints,
    write_metadata_to_notebook,
)
from mkprof.notebook import lint as nb_lint
from mkprof.notebook.markdown import (
    extract_metadata as extract_md_metadata,
    peek_hints as peek_md_hints,
    write_metadata as write_md_metadata,
)


def run_convert(cfg: MkprofConfig) -> int:
    """
    Headless notebook conversion for CI/scripting.

    Skips notebooks with missing metadata rather than prompting.
    Returns the number of conversion failures (0 = success).
    """
    from rich.console import Console
    console = Console()

    posts_dir = cfg.posts_dir
    notebooks = sorted(
        p for p in posts_dir.glob("*.ipynb")
        if ".ipynb_checkpoints" not in str(p)
    )

    if not notebooks:
        console.print(f"[dim]No notebooks found in {posts_dir}[/dim]")
        return 0

    console.print(
        f"Found [bold]{len(notebooks)}[/bold] notebook(s) in [cyan]{posts_dir}[/cyan]"
    )

    failed = 0
    for nb_path in notebooks:
        if extract_nb_metadata(nb_path) is None:
            console.print(f"[yellow]  skip[/yellow]  {nb_path.name}  (no metadata — run mkprof interactively to add it)")
            continue

        out_md = nb_path.with_suffix(".md")
        if out_md.exists() and out_md.stat().st_mtime >= nb_path.stat().st_mtime:
            console.print(f"[dim]  up-to-date[/dim]  {nb_path.name}")
            continue

        console.print(f"[cyan]  converting[/cyan]  {nb_path.name} …", end="")
        try:
            t0 = time.monotonic()
            post = parse_nb(nb_path, cfg.docs_dir)
            out_md, images = render_nb(post, nb_path, cfg.docs_dir)
            elapsed = time.monotonic() - t0
            console.print(f"  [green]✓[/green] [dim]({elapsed:.1f}s)[/dim]")
            if images:
                console.print(f"    [dim]{len(images)} image(s) → {nb_path.stem}_files/[/dim]")
            for w in post.asset_warnings:
                console.print(f"    [yellow]⚠  {w}[/yellow]")
        except Exception as exc:
            console.print(f"  [red]✗  {markup_escape(str(exc))}[/red]")
            failed += 1

    return failed


def _parse_date(s: str) -> date_type | None:
    normalized = s.strip().replace("/", "-").replace(".", "-")
    try:
        return datetime.datetime.fromisoformat(normalized).date()
    except ValueError:
        pass
    try:
        return datetime.datetime.strptime(normalized, "%Y-%m-%d").date()
    except ValueError:
        return None


def move_to_drafts(nb_path: Path, drafts_dir: Path) -> Path:
    drafts_dir.mkdir(parents=True, exist_ok=True)
    dest = drafts_dir / nb_path.name
    shutil.move(str(nb_path), dest)
    return dest


# ── Textual screens ───────────────────────────────────────────────────────────

class _DescriptionArea(TextArea):
    """Multi-line description field — Tab moves to next field instead of indenting."""
    BINDINGS = [
        Binding("tab", "screen.focus_next", "Next field", priority=True),
        Binding("shift+tab", "screen.focus_previous", "Prev field", priority=True),
    ]


class ArrowButton(Button):
    """Button with ▶ focus indicator and consistent white text on all variants.

    Button's component CSS applies a near-black ``$button-color-foreground`` to
    colored variants and ``text-style: reverse`` on focus.  Subclassing gives
    DEFAULT_CSS rules here equal-tier priority; variant-matched selectors then
    override those values by source order (subclass CSS is appended last).

    Labels carry two spaces of padding on each side.  On focus the leading pair
    becomes ``▶ `` so button width stays constant and the layout never reflows.
    """

    BINDINGS = [Binding("space", "press", "Press button", show=False)]

    DEFAULT_CSS = """
    ArrowButton {
        min-width: 0;
        content-align: left middle;
    }
    ArrowButton.-style-default.-success { color: white; }
    ArrowButton.-style-default.-primary { color: white; }
    ArrowButton.-style-default.-warning { color: white; }
    ArrowButton.-style-default.-error   { color: white; }
    ArrowButton.-style-default:focus    { text-style: bold; }
    """

    def __init__(self, label: str, **kwargs) -> None:
        self._base_label = label
        super().__init__(f"  {label}  ", **kwargs)

    def on_focus(self) -> None:
        self.label = f"▶ {self._base_label}  "

    def on_blur(self) -> None:
        self.label = f"  {self._base_label}  "


class MetadataModal(ModalScreen[dict | str | None]):
    """Prompt the user to fill in missing blog metadata or skip to drafts."""

    # Layout thresholds (terminal rows)
    _REPL_THRESHOLD = 18           # below → suspend TUI, fall back to plain input() prompts
    _ULTRA_COMPACT_THRESHOLD = 25  # below → labeled-row compact layout (= _DIALOG_MIN_HEIGHT)

    # Row budget for the normal scrollable layout:
    #   overhead = round-border×2 (2) + btn-margin (1) + buttons (3)
    #              (title embedded in border; no padding, no Rule, no body-margin)
    #   fixed scroll content = title/date-row (4) + desc-label+margin (2)
    #              + tags/slug-row+margin (5) + authors-label (1)
    #              + authors-list max-height:3 (3) + spell-check-label (1)
    #   minimum dialog = overhead + fixed + desc_min = 6 + 16 + 3 = 25
    #   desc_min = 3: border-top + 1 text row + border-bottom (same as other Input fields)
    _DIALOG_OVERHEAD = 6
    _SCROLL_FIXED = 16
    _DIALOG_MIN_HEIGHT = 25   # mirrors min-height in DEFAULT_CSS #dialog rule
    _DESC_MAX = 8

    DEFAULT_CSS = """
    MetadataModal {
        align: center middle;
    }
    #dialog {
        width: 78;
        height: 85%;
        min-height: 25;
        padding: 0 2;
        background: $background;
        border: round $primary;
        border-title-align: left;
        border-title-color: $warning;
        border-title-style: bold;
    }
    #dialog-body {
        height: 1fr;
    }
    /* Explicitly zero out all margins inside the scroll body.
       Textual's DEFAULT_CSS for TextArea, SelectionList, etc. can add
       implicit margins that compound into large gaps inside a scroll area. */
    #row-title-date, #row-tags-slug,
    #col-title, #col-date, #col-tags, #col-slug,
    #f-title, #f-date, #f-desc, #f-tags, #f-slug,
    #f-authors, #f-authors-list {
        margin: 0;
    }
    .field-label, .col-label {
        color: $text-muted;
        margin: 0;
    }
    #col-title, #col-tags {
        width: 2fr;
        padding-right: 2;
    }
    #col-date, #col-slug {
        width: 1fr;
    }
    /* One line of breathing room before the second field group */
    #row-tags-slug {
        margin-top: 1;
    }
    /* Description: height set dynamically by _apply_layout; 3 is the minimum (1 text row + borders) */
    #f-desc {
        height: 3;
    }
    #f-authors-list {
        max-height: 3;
        border: solid $surface-lighten-2;
        background: $surface-darken-1;
    }
    #word-list-scroll {
        max-height: 5;
        border: solid $surface-lighten-2;
        background: $surface-darken-1;
        padding: 0 1;
        margin: 0;
    }
    #word-list {
        color: $warning;
    }
    #buttons {
        margin-top: 1;
        height: auto;
        align: center middle;
    }
    #btn-add  { margin-right: 2; }
    #btn-skip { margin-right: 2; }

    /* Description label: one row of breathing room above the field */
    #desc-label {
        margin-top: 1;
    }
    /* REPL fallback: hide TUI chrome while plain input() prompts run */
    MetadataModal.repl-mode #dialog {
        display: none;
    }

    /* ── Ultra-compact mode: labeled rows, 1 row per field, no input chrome ── */
    /* Hidden by default; activated when MetadataModal gains .ultra-compact      */
    #ultra-body {
        display: none;
        height: auto;
        margin-top: 1;
    }
    .uc-row {
        height: 1;
        margin: 0;
    }
    #uc-authors-list {
        width: 1fr;
        height: 1;
        min-height: 1;
        border: none;
        background: $boost;
    }
    .uc-label {
        width: 14;
        text-align: right;
        color: $text-muted;
        margin: 0;
        padding: 0;
    }
    Input.uc-input {
        width: 1fr;
        border: none;
        background: $boost;
        height: 1;
        min-height: 1;
        margin: 0;
        padding: 0 1;
    }
    MetadataModal.ultra-compact #dialog {
        height: auto;
        min-height: 0;
    }
    MetadataModal.ultra-compact #dialog-body {
        display: none;
    }
    MetadataModal.ultra-compact #ultra-body {
        display: block;
    }
    """

    def __init__(
        self,
        file_path: Path,
        hints: dict | None = None,
        unknown_words: list[str] | None = None,
        default_author: str = "",
        available_authors: list[tuple[str, str]] | None = None,
        idx: int = 0,
        total: int = 0,
    ) -> None:
        super().__init__()
        self.file_path = file_path
        self.hints = hints or {}
        self.unknown_words = unknown_words or []
        self.default_author = default_author
        self.available_authors = available_authors or []
        self.idx = idx
        self.total = total
        self._draft_armed = False

    def compose(self) -> ComposeResult:
        stem = self.file_path.stem
        today = str(date_type.today())

        default_title = self.hints.get("title") or stem.replace("-", " ").replace("_", " ").title()
        default_desc = self.hints.get("description") or ""

        raw_date = self.hints.get("date")
        default_date = str(raw_date)[:10] if raw_date else today

        tags_hint = self.hints.get("tags", "")
        if isinstance(tags_hint, list):
            tags_hint = ", ".join(str(t) for t in tags_hint)

        authors_hint = self.hints.get("authors", [self.default_author] if self.default_author else [])
        if isinstance(authors_hint, list):
            authors_hint = " ".join(authors_hint)
        if not authors_hint:
            authors_hint = self.default_author

        # Precompute preselected author slugs — used by both normal and UC SelectionList.
        hints_authors = self.hints.get("authors")
        if hints_authors is None:
            preselected = {self.default_author} if self.default_author else set()
        elif isinstance(hints_authors, list):
            preselected = set(hints_authors)
        else:
            preselected = {str(hints_authors)}

        slug_hint = self.hints.get("slug") or ""
        btn_label = "Add Metadata"

        progress = f"  [{self.idx} of {self.total}]" if self.total > 1 else ""
        with Container(id="dialog") as dialog:
            dialog.border_title = f"No metadata found: {self.file_path.name}{progress}"

            # Form body: 1fr so it claims all space between the border title
            # above and the buttons below.  VerticalScroll handles overflow on
            # tight terminals; Tab navigation auto-scrolls to the focused field.
            with VerticalScroll(id="dialog-body"):
                # Row 1: Title (wide) + Date (narrow)
                with Horizontal(id="row-title-date"):
                    with Vertical(id="col-title"):
                        yield Label("Title  [red]*[/red]", classes="col-label", markup=True)
                        yield Input(value=default_title, id="f-title")
                    with Vertical(id="col-date"):
                        yield Label("Date  [red]*[/red]", classes="col-label", markup=True)
                        yield Input(value=default_date, placeholder="YYYY-MM-DD", id="f-date")

                yield Label("Description", classes="field-label", id="desc-label")
                yield _DescriptionArea(
                    text=default_desc,
                    id="f-desc",
                    show_line_numbers=False,
                )

                # Row 2: Tags (wide) + Slug (narrow)
                with Horizontal(id="row-tags-slug"):
                    with Vertical(id="col-tags"):
                        yield Label("Tags  (comma-separated)", classes="col-label")
                        yield Input(value=tags_hint, placeholder="python, biology, math", id="f-tags")
                    with Vertical(id="col-slug"):
                        yield Label("Slug  (blank = from filename)", classes="col-label")
                        yield Input(value=slug_hint, placeholder=stem, id="f-slug")

                if self.available_authors:
                    yield Label("Authors", classes="field-label")
                    yield SelectionList(
                        *[
                            (f"{markup_escape(name)}  [dim]({markup_escape(slug)})[/dim]", slug, slug in preselected)
                            for slug, name in self.available_authors
                        ],
                        id="f-authors-list",
                    )
                else:
                    yield Label("Authors  (space-separated slugs from authors.yml)", classes="field-label")
                    yield Input(value=authors_hint, id="f-authors")

                if self.unknown_words:
                    n = len(self.unknown_words)
                    yield Label(
                        f"Spell check — [yellow]{n}[/yellow] unknown word{'s' if n != 1 else ''}",
                        classes="field-label",
                        markup=True,
                    )
                    with VerticalScroll(id="word-list-scroll"):
                        yield Static("  ".join(self.unknown_words), id="word-list")
                else:
                    yield Label(
                        "Spell check — [green]✓ no unknown words[/green]",
                        classes="field-label",
                        markup=True,
                    )

            # Ultra-compact layout: labeled rows, 1 row per field, no input borders.
            # Activated when .ultra-compact class is added to the modal.
            # Fields ordered by fill-priority: content first, metadata after.
            with Container(id="ultra-body"):
                with Horizontal(classes="uc-row"):
                    yield Label("Title :", classes="uc-label")
                    yield Input(value=default_title, id="uc-title", classes="uc-input")
                with Horizontal(classes="uc-row"):
                    yield Label("Description :", classes="uc-label")
                    yield Input(value=default_desc, id="uc-desc", classes="uc-input")
                with Horizontal(classes="uc-row"):
                    yield Label("Tags :", classes="uc-label")
                    yield Input(value=tags_hint, id="uc-tags", classes="uc-input")
                with Horizontal(classes="uc-row"):
                    yield Label("Slug :", classes="uc-label")
                    yield Input(value=slug_hint, placeholder=stem, id="uc-slug", classes="uc-input")
                with Horizontal(classes="uc-row"):
                    yield Label("Date :", classes="uc-label")
                    yield Input(value=default_date, id="uc-date", classes="uc-input")
                if self.available_authors:
                    with Horizontal(classes="uc-row"):
                        yield Label("Authors :", classes="uc-label")
                        yield SelectionList(
                            *[
                                (f"{markup_escape(name)}  [dim]({markup_escape(slug)})[/dim]", slug, slug in preselected)
                                for slug, name in self.available_authors
                            ],
                            id="uc-authors-list",
                        )
                else:
                    with Horizontal(classes="uc-row"):
                        yield Label("Authors :", classes="uc-label")
                        yield Input(value=authors_hint, id="uc-authors", classes="uc-input")

            # Buttons pinned outside the scroll so they're always visible.
            with Horizontal(id="buttons"):
                yield ArrowButton(btn_label, variant="success", id="btn-add")
                yield ArrowButton("Skip for now", variant="primary", id="btn-skip")
                yield ArrowButton("Save to Drafts", variant="warning", id="btn-draft")

    def _apply_layout(self) -> None:
        """Resize variable elements; collapse priority: spell check → description → ultra-compact.

        The modal is always rendered completely or switched to ultra-compact.
        _DIALOG_MIN_HEIGHT / min-height in CSS ensures the dialog never clips
        its own chrome; description grows from 3 rows (minimum) upward as space allows.
        """
        screen_h = self.app.size.height
        if screen_h < self._ULTRA_COMPACT_THRESHOLD:
            self.add_class("ultra-compact")
            return
        self.remove_class("ultra-compact")

        wl_min = 2 if self.unknown_words else 0
        available = (
            max(self._DIALOG_MIN_HEIGHT, int(screen_h * 0.85))
            - self._DIALOG_OVERHEAD
            - self._SCROLL_FIXED
        )

        # Spell check collapses first: description gets priority, spell check uses remainder.
        # Minimum 3: border-top + 1 text row + border-bottom (matches other Input fields).
        desc_h = max(3, min(self._DESC_MAX, available - wl_min))
        wl_h = max(wl_min, min(5, available - desc_h)) if self.unknown_words else 0

        self.query_one("#f-desc").styles.height = desc_h
        if self.unknown_words:
            self.query_one("#word-list-scroll").styles.max_height = wl_h

    def on_mount(self) -> None:
        # Belt-and-suspenders: Textual's component CSS can win over DEFAULT_CSS
        # for border/height on these widgets, so also set these imperatively.
        for inp in self.query("Input.uc-input").results(Input):
            inp.styles.border = ("none", "transparent")
            inp.styles.height = 1
        for sl in self.query("#uc-authors-list").results(SelectionList):
            sl.styles.border = ("none", "transparent")
            sl.styles.height = 1

        self._apply_layout()
        if self.app.size.height < self._REPL_THRESHOLD:
            self.add_class("repl-mode")
            self._run_repl()
            return
        self.query_one("#dialog-body", VerticalScroll).scroll_home(animate=False)

    def on_resize(self) -> None:
        self._apply_layout()

    @work(thread=True)
    def _run_repl(self) -> None:
        """Collect metadata via plain input() prompts when the terminal is too small for TUI."""
        stem = self.file_path.stem
        default_title = (
            self.hints.get("title") or stem.replace("-", " ").replace("_", " ").title()
        )
        raw_date = self.hints.get("date")
        default_date = str(raw_date)[:10] if raw_date else str(date_type.today())
        default_desc = self.hints.get("description") or ""
        tags_hint = self.hints.get("tags", "")
        if isinstance(tags_hint, list):
            tags_hint = ", ".join(str(t) for t in tags_hint)
        default_authors = self.default_author or ""

        with self.app.suspend():
            print(f"\n  {self.file_path.name}")
            title   = input(f"  Title   [{default_title}]: ").strip() or default_title
            date_s  = input(f"  Date    [{default_date}]: ").strip() or default_date
            desc    = input(f"  Desc    [{default_desc}]: ").strip() or default_desc
            tags    = input(f"  Tags    [{tags_hint}]: ").strip() or tags_hint
            authors = input(f"  Authors [{default_authors}]: ").strip() or default_authors
            slug    = input( "  Slug    (blank=auto): ").strip()
            action  = input("  Enter=save  s=skip  d=drafts : ").strip().lower()
            print()

        if action == "s":
            self.app.call_from_thread(self.dismiss, "skip")
            return
        if action == "d":
            self.app.call_from_thread(self.dismiss, None)
            return

        post_date = _parse_date(date_s) or date_type.today()
        meta: dict = {"title": title, "date": post_date}
        if desc:
            meta["description"] = desc
        if tags:
            meta["tags"] = [t.strip() for t in tags.split(",") if t.strip()]
        if authors:
            meta["authors"] = authors.split()
        if slug:
            meta["slug"] = slug

        if self.file_path.suffix == ".ipynb":
            write_metadata_to_notebook(self.file_path, meta)
        else:
            write_md_metadata(self.file_path, meta)
        self.app.call_from_thread(self.dismiss, meta)

    @on(Button.Pressed, "#btn-add")
    def handle_add(self) -> None:
        ultra = self.has_class("ultra-compact")

        if ultra:
            title = self.query_one("#uc-title", Input).value.strip()
            raw_date = self.query_one("#uc-date", Input).value.strip()
        else:
            title = self.query_one("#f-title", Input).value.strip()
            raw_date = self.query_one("#f-date", Input).value.strip()

        if not title or not raw_date:
            self.query_one("#dialog").border_title = "[red]Title and Date are required.[/red]"
            return

        post_date = _parse_date(raw_date)
        if post_date is None:
            self.query_one("#dialog").border_title = (
                f"[red]Invalid date '{markup_escape(raw_date)}' — use YYYY-MM-DD.[/red]"
            )
            return

        meta: dict = {"title": title, "date": post_date}

        if ultra:
            desc = self.query_one("#uc-desc", Input).value.strip()
        else:
            desc = self.query_one("#f-desc", _DescriptionArea).text.strip()
        if desc:
            meta["description"] = desc

        if ultra:
            tags_raw = self.query_one("#uc-tags", Input).value.strip()
        else:
            tags_raw = self.query_one("#f-tags", Input).value.strip()
        if tags_raw:
            meta["tags"] = [t.strip() for t in tags_raw.split(",") if t.strip()]

        if ultra and self.available_authors:
            selected = self.query_one("#uc-authors-list", SelectionList).selected
            if selected:
                meta["authors"] = list(selected)
        elif ultra:
            authors_raw = self.query_one("#uc-authors", Input).value.strip()
            if authors_raw:
                meta["authors"] = authors_raw.split()
        elif self.available_authors:
            selected = self.query_one("#f-authors-list", SelectionList).selected
            if selected:
                meta["authors"] = list(selected)
        else:
            authors_raw = self.query_one("#f-authors", Input).value.strip()
            if authors_raw:
                meta["authors"] = authors_raw.split()

        if ultra:
            slug = self.query_one("#uc-slug", Input).value.strip()
        else:
            slug = self.query_one("#f-slug", Input).value.strip()
        if slug:
            meta["slug"] = slug

        if self.file_path.suffix == ".ipynb":
            write_metadata_to_notebook(self.file_path, meta)
        else:
            write_md_metadata(self.file_path, meta)
        self.dismiss(meta)

    @on(Button.Pressed, "#btn-skip")
    def handle_skip(self) -> None:
        self.dismiss("skip")

    @on(Button.Pressed, "#btn-draft")
    def handle_draft(self) -> None:
        btn = self.query_one("#btn-draft", ArrowButton)
        if not self._draft_armed:
            self._draft_armed = True
            btn._base_label = "⚠ Confirm?"
            btn.label = f"▶ ⚠ Confirm?  "
            btn.variant = "error"
        else:
            self.dismiss(None)


# ── Main application ──────────────────────────────────────────────────────────

class BuildApp(App[None]):
    BINDINGS = [Binding("q", "quit", "Quit")]
    CSS = """
    Screen { background: $background; }
    RichLog {
        padding: 0 1;
        background: $background;
        scrollbar-size: 0 0;
    }
    #action-bar {
        height: auto;
        padding: 1 2;
        background: $background;
        border: round $primary;
        border-title-align: center;
        border-title-color: $success;
        border-title-style: bold;
        display: none;
    }
    #action-bar-buttons {
        align: center middle;
        height: auto;
    }
    #btn-action-build { margin-right: 2; }
    #btn-action-serve { margin-right: 2; }
    """

    def __init__(self, cfg: MkprofConfig, mode: str = "build") -> None:
        super().__init__()
        self.cfg = cfg
        self.mode = mode  # "build" | "serve" | "convert"
        self._serve_proc: asyncio.subprocess.Process | None = None
        self._build_proc: asyncio.subprocess.Process | None = None
        self._exiting = False
        self._action_event: asyncio.Event = asyncio.Event()
        self._action_result: str = ""

    def compose(self) -> ComposeResult:
        yield Header()
        yield RichLog(id="log", highlight=True, markup=True, wrap=True)
        with Container(id="action-bar"):
            with Horizontal(id="action-bar-buttons"):
                yield ArrowButton("Build Site", variant="success", id="btn-action-build")
                yield ArrowButton("Start Dev Server", variant="primary", id="btn-action-serve")
                yield ArrowButton("Quit", variant="error", id="btn-action-quit")
        yield Footer()

    def on_mount(self) -> None:
        self.title = self.cfg.site_name
        self.sub_title = {"build": "build", "serve": "dev server", "convert": "convert only"}.get(self.mode, self.mode)
        self.run_worker(self._pipeline(), exclusive=True, name="builder")

    def _log(self, msg: str) -> None:
        self.query_one(RichLog).write(msg)

    async def on_unmount(self) -> None:
        for proc in (self._serve_proc, self._build_proc):
            if proc is not None:
                try:
                    proc.kill()
                    await asyncio.wait_for(proc.wait(), timeout=2.0)
                except Exception:
                    pass

    async def _show_action_menu(self, title: str) -> str:
        self._action_event.clear()
        self._action_result = ""
        self.query_one("#action-bar").border_title = title
        self.query_one("#action-bar").display = True
        self.query_one("#btn-action-build", Button).focus()
        await self._action_event.wait()
        self.query_one("#action-bar").display = False
        return self._action_result

    def on_key(self, event) -> None:
        if not self.query_one("#action-bar").display:
            return
        build = self.query_one("#btn-action-build", Button)
        serve = self.query_one("#btn-action-serve", Button)
        quit_ = self.query_one("#btn-action-quit", Button)
        if event.key in ("right", "tab"):
            if self.focused is build:
                serve.focus()
                event.prevent_default()
            elif self.focused is serve:
                quit_.focus()
                event.prevent_default()
        elif event.key in ("left", "shift+tab"):
            if self.focused is serve:
                build.focus()
                event.prevent_default()
            elif self.focused is quit_:
                serve.focus()
                event.prevent_default()

    @on(Button.Pressed, "#btn-action-build")
    def _press_action_build(self) -> None:
        self._action_result = "build"
        self._action_event.set()

    @on(Button.Pressed, "#btn-action-serve")
    def _press_action_serve(self) -> None:
        self._action_result = "serve"
        self._action_event.set()

    @on(Button.Pressed, "#btn-action-quit")
    def _press_action_quit(self) -> None:
        self._action_result = "quit"
        self._action_event.set()

    def on_screen_suspend(self) -> None:
        try:
            self.query_one(RichLog).auto_scroll = False
        except Exception:
            pass

    def on_screen_resume(self) -> None:
        try:
            log = self.query_one(RichLog)
            log.auto_scroll = True
            log.scroll_end(animate=False)
        except Exception:
            pass

    # ── Pipeline stages ───────────────────────────────────────────────────────

    def _log_lint(self, issues: list[nb_lint.LintIssue]) -> None:
        colors = {"info": "dim", "warn": "yellow", "error": "red"}
        for issue in issues:
            col = colors.get(issue.level, "white")
            loc = f":{issue.line}" if issue.line else ""
            tag = " [dim](fixed)[/dim]" if issue.fixed else ""
            self._log(f"   [{col}]{issue.check}{loc}: {issue.message}[/{col}]{tag}")

    def _log_external(self, line: str) -> None:
        escaped = markup_escape(line)
        upper = line.upper()
        if any(kw in upper for kw in ("ERROR", "CRITICAL")):
            self._log(f"[red]{escaped}[/red]")
        elif "WARNING" in upper:
            self._log(f"[yellow]{escaped}[/yellow]")
        else:
            self._log(f"[dim]{escaped}[/dim]")

    async def _ensure_metadata(
        self, path: Path, *, is_notebook: bool, idx: int = 0, total: int = 0
    ) -> bool:
        extract_fn = extract_nb_metadata if is_notebook else extract_md_metadata
        peek_fn = peek_nb_hints if is_notebook else peek_md_hints

        if extract_fn(path) is not None:
            return True

        self._log(f"\n[yellow]⚠  Missing metadata:[/yellow] [bold]{path.name}[/bold]")
        unknown_words = nb_lint.get_unknown_words(path)
        result = await self.push_screen_wait(
            MetadataModal(
                path,
                peek_fn(path),
                unknown_words=unknown_words,
                default_author=self.cfg.default_author,
                available_authors=list(self.cfg.authors.items()),
                idx=idx,
                total=total,
            )
        )
        if result is None:
            dest = move_to_drafts(path, self.cfg.drafts_dir)
            self._log(f"   [yellow]→ Moved to drafts: {dest}[/yellow]")
            return False
        if result == "skip":
            self._log("   [dim]→ Skipped[/dim]")
            return False
        self._log(
            "   [green]✓  Metadata written to notebook[/green]"
            if is_notebook else
            "   [green]✓  Metadata written[/green]"
        )
        return True

    async def _convert_articles(self) -> None:
        posts_dir = self.cfg.posts_dir
        notebooks = sorted(
            p for p in posts_dir.glob("*.ipynb")
            if ".ipynb_checkpoints" not in str(p)
        )
        markdowns = sorted(
            p for p in posts_dir.glob("*.md")
            if not p.with_suffix(".ipynb").exists()
        )

        if not notebooks and not markdowns:
            self._log(f"[yellow]No articles found in {posts_dir}[/yellow]")
            return

        self._log(
            f"Found [bold]{len(notebooks)}[/bold] notebook(s) and "
            f"[bold]{len(markdowns)}[/bold] markdown file(s) in "
            f"[cyan]{posts_dir}[/cyan]\n"
        )

        total = len(notebooks) + len(markdowns)

        for i, nb_path in enumerate(notebooks, 1):
            if not await self._ensure_metadata(nb_path, is_notebook=True, idx=i, total=total):
                continue
            out_md = nb_path.with_suffix(".md")
            if out_md.exists() and out_md.stat().st_mtime >= nb_path.stat().st_mtime:
                self._log(f"\n[dim]Skipping[/dim] {nb_path.name} [dim](markdown is up to date)[/dim]")
                continue
            self._log(f"\n[cyan]Converting[/cyan] {nb_path.name} …")
            try:
                t0 = time.monotonic()
                post = parse_nb(nb_path, self.cfg.docs_dir)
                out_md, images = render_nb(post, nb_path, self.cfg.docs_dir)
                elapsed = time.monotonic() - t0
                self._log(f"   [green]✓[/green] {out_md.name} [dim]({elapsed:.1f}s)[/dim]")
                if images:
                    self._log(
                        f"   [dim]{len(images)} image(s) → "
                        f"{nb_path.stem}_files/[/dim]"
                    )
                for w in post.asset_warnings:
                    self._log(f"   [yellow]⚠  asset path: {w}[/yellow]")
            except Exception as exc:
                self._log(f"   [red]✗  {markup_escape(str(exc))}[/red]")

        for i, md_path in enumerate(markdowns, len(notebooks) + 1):
            if not await self._ensure_metadata(md_path, is_notebook=False, idx=i, total=total):
                continue
            issues = nb_lint.run_checks(md_path)
            if issues:
                self._log(f"\n[dim]{md_path.name}[/dim]")
                self._log_lint(issues)

    async def _run_mkdocs_build(self) -> bool:
        self._log(f"\n[bold]Running:[/bold] mkdocs build\n{'─' * 60}")
        proc = await asyncio.create_subprocess_exec(
            "mkdocs", "build",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        self._build_proc = proc
        assert proc.stdout
        try:
            async for raw in proc.stdout:
                self._log_external(raw.decode().rstrip())
            rc = await proc.wait()
        finally:
            self._build_proc = None
        if rc != 0:
            self._log(f"\n[bold red]mkdocs build failed (exit {rc}).[/bold red]")
        return rc == 0

    async def _run_mkdocs_serve(self) -> None:
        killer = await asyncio.create_subprocess_exec(
            "pkill", "-f", "mkdocs serve",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await killer.wait()
        if killer.returncode == 0:
            self._log("[dim]Killed existing mkdocs serve process.[/dim]")
            await asyncio.sleep(0.5)

        self._log(
            "\n[bold]Starting dev server[/bold] — "
            "press [bold]q[/bold] to stop.\n" + "─" * 60
        )
        try:
            proc = await asyncio.create_subprocess_exec(
                "mkdocs", "serve",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
        except Exception:
            self._log(
                "[bold red]Failed to start mkdocs serve:[/bold red]\n"
                + markup_escape(traceback.format_exc())
            )
            return
        self._serve_proc = proc
        assert proc.stdout
        try:
            async for raw in proc.stdout:
                self._log_external(raw.decode().rstrip())
        except Exception:
            self._log("[red]Error reading server output:[/red]\n" + markup_escape(traceback.format_exc()))
        finally:
            await proc.wait()
            self._serve_proc = None
        self._log("\n[dim]Dev server stopped.[/dim]")

    # ── Top-level orchestration ───────────────────────────────────────────────

    async def _pipeline(self) -> None:
        try:
            await self._pipeline_inner()
        except asyncio.CancelledError:
            raise
        except Exception:
            self._log(
                "\n[bold red]Unexpected error:[/bold red]\n"
                + markup_escape(traceback.format_exc())
                + "\nPress [bold]q[/bold] to exit."
            )

    async def _pipeline_inner(self) -> None:
        await self._convert_articles()

        if self.mode == "convert":
            self._log(
                "\n[bold green]All notebooks converted.[/bold green]"
                "  Press [bold]q[/bold] to exit."
            )
            return

        if self.mode == "serve":
            await self._run_mkdocs_serve()
        else:
            self._log("\n[bold green]✓ Conversion complete[/bold green] — choose an action below.")
            action = await self._show_action_menu("Notebooks converted — ready")
            if action == "quit":
                self.exit()
                return
            if action == "serve":
                await self._run_mkdocs_serve()
            else:
                await self._run_mkdocs_build()
                self._log("\n[bold]Press [bold]q[/bold] to exit.[/bold]")
                return

        self._log("\n[bold]Server stopped.[/bold]  Press [bold]q[/bold] to exit.")

    # ── Clean shutdown ────────────────────────────────────────────────────────

    async def _stop_proc(self, proc: asyncio.subprocess.Process) -> None:
        proc.terminate()
        try:
            await asyncio.wait_for(proc.wait(), timeout=3.0)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()

    async def action_quit(self) -> None:
        self._exiting = True
        if self._serve_proc is not None:
            self._log("\n[dim]Stopping dev server…[/dim]")
            await self._stop_proc(self._serve_proc)
            self._serve_proc = None
        if self._build_proc is not None:
            self._log("\n[dim]Stopping build…[/dim]")
            await self._stop_proc(self._build_proc)
            self._build_proc = None
        self.exit()
