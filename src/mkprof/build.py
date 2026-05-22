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

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Header, Input, Label, RichLog, Rule, Static

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

class MetadataModal(ModalScreen[dict | str | None]):
    """Prompt the user to fill in missing blog metadata or skip to drafts."""

    DEFAULT_CSS = """
    MetadataModal {
        align: center middle;
    }
    #dialog {
        width: 72;
        height: auto;
        padding: 1 2;
        background: $surface;
        border: thick $primary;
    }
    #dialog-title {
        text-style: bold;
        color: $warning;
        margin-bottom: 1;
    }
    .field-label {
        color: $text-muted;
        margin-top: 1;
    }
    #buttons {
        margin-top: 2;
        height: auto;
    }
    #btn-add {
        margin-right: 2;
    }
    #btn-skip {
        margin-right: 1;
    }
    #word-list-scroll {
        max-height: 4;
        border: solid $surface-lighten-2;
        background: $surface-darken-1;
        padding: 0 1;
        margin-top: 0;
    }
    #word-list {
        color: $warning;
    }
    """

    def __init__(
        self,
        file_path: Path,
        hints: dict | None = None,
        unknown_words: list[str] | None = None,
        default_author: str = "",
        idx: int = 0,
        total: int = 0,
    ) -> None:
        super().__init__()
        self.file_path = file_path
        self.hints = hints or {}
        self.unknown_words = unknown_words or []
        self.default_author = default_author
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

        slug_hint = self.hints.get("slug") or ""
        btn_label = "Add Metadata & Convert" if self.file_path.suffix == ".ipynb" else "Add Metadata"

        progress = f"  [dim][{self.idx} of {self.total}][/dim]" if self.total > 1 else ""
        with Container(id="dialog"):
            yield Label(
                f"No metadata found: [bold]{self.file_path.name}[/bold]{progress}",
                id="dialog-title",
                markup=True,
            )
            yield Rule()
            yield Label("Title  [red]*[/red]", classes="field-label", markup=True)
            yield Input(value=default_title, id="f-title")
            yield Label(
                "Date  [red]*[/red]  (YYYY-MM-DD)",
                classes="field-label",
                markup=True,
            )
            yield Input(value=default_date, id="f-date")
            yield Label("Description", classes="field-label")
            yield Input(value=default_desc, placeholder="One-line summary shown in the blog index", id="f-desc")
            yield Label("Tags  (comma-separated)", classes="field-label")
            yield Input(value=tags_hint, placeholder="python, biology, math", id="f-tags")
            yield Label("Authors  (space-separated slugs from authors.yml)", classes="field-label")
            yield Input(value=authors_hint, id="f-authors")
            yield Label("Slug  (leave blank to derive from filename)", classes="field-label")
            yield Input(value=slug_hint, placeholder=stem, id="f-slug")
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
            with Horizontal(id="buttons"):
                yield Button(btn_label, variant="primary", id="btn-add")
                yield Button("Skip for now", id="btn-skip")
                yield Button("→ Drafts", variant="warning", id="btn-draft")

    @on(Button.Pressed, "#btn-add")
    def handle_add(self) -> None:
        title = self.query_one("#f-title", Input).value.strip()
        raw_date = self.query_one("#f-date", Input).value.strip()

        if not title or not raw_date:
            self.query_one("#dialog-title", Label).update(
                "[red]Title and Date are required.[/red]"
            )
            return

        post_date = _parse_date(raw_date)
        if post_date is None:
            self.query_one("#dialog-title", Label).update(
                f"[red]Invalid date '{markup_escape(raw_date)}' — use YYYY-MM-DD.[/red]"
            )
            return

        meta: dict = {"title": title, "date": post_date}

        desc = self.query_one("#f-desc", Input).value.strip()
        if desc:
            meta["description"] = desc

        tags_raw = self.query_one("#f-tags", Input).value.strip()
        if tags_raw:
            meta["tags"] = [t.strip() for t in tags_raw.split(",") if t.strip()]

        authors_raw = self.query_one("#f-authors", Input).value.strip()
        if authors_raw:
            meta["authors"] = authors_raw.split()

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
        btn = self.query_one("#btn-draft", Button)
        if not self._draft_armed:
            self._draft_armed = True
            btn.label = "⚠ Confirm move?"
            btn.variant = "error"
        else:
            self.dismiss(None)


# ── Main application ──────────────────────────────────────────────────────────

class BuildApp(App[None]):
    BINDINGS = [Binding("q", "quit", "Quit")]
    CSS = """
    Screen { background: $background; }
    RichLog { padding: 0 1; }
    #action-bar {
        height: auto;
        padding: 1 2;
        background: $surface;
        border-top: thick $success;
        display: none;
    }
    #action-bar-title {
        text-align: center;
        text-style: bold;
        color: $success;
    }
    #action-bar-buttons {
        align: center middle;
        height: auto;
        margin-top: 1;
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
        yield RichLog(id="log", highlight=True, markup=True)
        with Container(id="action-bar"):
            yield Label("", id="action-bar-title")
            yield Rule()
            with Horizontal(id="action-bar-buttons"):
                yield Button("Build Site", variant="default", id="btn-action-build")
                yield Button("Start Dev Server", variant="primary", id="btn-action-serve")
                yield Button("Quit", variant="error", id="btn-action-quit")
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
        self.query_one("#action-bar-title", Label).update(title)
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
        elif event.key in ("space", "enter"):
            if self.focused is build:
                self._press_action_build()
            elif self.focused is serve:
                self._press_action_serve()
            elif self.focused is quit_:
                self._press_action_quit()

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
        colours = {"info": "dim", "warn": "yellow", "error": "red"}
        for issue in issues:
            col = colours.get(issue.level, "white")
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
