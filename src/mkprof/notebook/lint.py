"""
notebook/lint.py — Markdown linting and formatting checks for blog articles.

Each LintCheck subclass implements run(path, content) -> list[LintIssue].
Checks with auto_fix=True may rewrite the file and mark issues as fixed=True.

run_checks() re-reads the file after any auto-fix so subsequent checks see
the updated content.

Spell check is intentionally separate: get_unknown_words() returns prose words
not found in the dictionary for human review — it does not produce LintIssues.
Add project-specific technical terms to .spell-ignore.txt (one word per line)
to suppress them permanently.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import mdformat
from spellchecker import SpellChecker


SPELL_IGNORE_FILE = Path(".spell-ignore.txt")

_UNAVAILABLE_MATHJAX_COMMANDS = frozenset({
    r"\mathclap",       # mathtools
    r"\bm",             # bm package
    r"\shortintertext", # mathtools
    r"\prescript",      # mathtools
})


# ── Issue dataclass ───────────────────────────────────────────────────────────

@dataclass
class LintIssue:
    level: str          # "info" | "warn" | "error"
    check: str          # short check name shown in the log
    message: str
    line: int | None = None
    fixed: bool = False


# ── Base class ────────────────────────────────────────────────────────────────

class LintCheck:
    name: str = ""
    auto_fix: bool = False

    def run(self, _path: Path, _content: str) -> list[LintIssue]:
        return []


# ── Concrete checks ───────────────────────────────────────────────────────────

def _protect_math(text: str) -> tuple[str, dict[str, str]]:
    """Replace math blocks with opaque placeholders so mdformat doesn't escape them."""
    saved: dict[str, str] = {}
    counter = [0]

    def _save(m: re.Match) -> str:
        key = f"XMATHPLACEHOLDERX{counter[0]:04d}X"
        counter[0] += 1
        saved[key] = m.group(0)
        return key

    # Display math first (may span multiple lines)
    text = re.sub(r"\$\$[\s\S]*?\$\$", _save, text)
    # Inline math (single-line only)
    text = re.sub(r"\$[^$\n]{1,200}\$", _save, text)
    return text, saved


def _restore_math(text: str, saved: dict[str, str]) -> str:
    for key, value in saved.items():
        text = text.replace(key, value)
    return text


class MdformatCheck(LintCheck):
    """Auto-format Markdown body with mdformat; frontmatter is left untouched."""

    name = "mdformat"
    auto_fix = True

    _FRONT_RE = re.compile(r"^---\n.*?\n---\n?", re.DOTALL)

    def run(self, path: Path, content: str) -> list[LintIssue]:
        # Peel off the YAML block so mdformat never sees it — without the
        # frontmatter plugin active it treats --- as a thematic break; with
        # it active ruamel.yaml reformats YAML style in ways we don't want.
        front = ""
        body = content
        m = self._FRONT_RE.match(content)
        if m:
            front = m.group(0).rstrip("\n") + "\n"
            body = content[m.end():]

        # Shield math blocks from mdformat — it doesn't understand LaTeX and
        # would escape backslashes inside $...$ and $$...$$ spans.
        body, math_saved = _protect_math(body)

        try:
            formatted_body = mdformat.text(body) if body.strip() else ""
        except Exception as exc:
            return [LintIssue("warn", self.name, f"formatter error: {exc}")]

        formatted_body = _restore_math(formatted_body, math_saved)

        # Keep a blank line between frontmatter and body.
        if front and formatted_body and not formatted_body.startswith("\n"):
            formatted_body = "\n" + formatted_body

        formatted = front + formatted_body
        if formatted == content:
            return []
        path.write_text(formatted, encoding="utf-8")
        return [LintIssue("info", self.name, "reformatted", fixed=True)]


class NbFigCheck(LintCheck):
    """Warn when Markdown images or <img> tags are missing the .nb-fig class."""

    name = "nb-fig"

    def run(self, _path: Path, content: str) -> list[LintIssue]:
        issues = []
        in_fence = False
        for i, line in enumerate(content.splitlines(), 1):
            stripped = line.strip()
            if re.match(r"^(?:```|~~~)", stripped):
                in_fence = not in_fence
            if in_fence:
                continue
            if re.search(r"!\[[^\]]*\]\([^\)]+\)", line) and ".nb-fig" not in line:
                issues.append(LintIssue("warn", self.name,
                    f"image without .nb-fig: {stripped[:60]}", line=i))
            if re.search(r"<img\b", line, re.IGNORECASE) and "nb-fig" not in line:
                issues.append(LintIssue("warn", self.name,
                    f'<img> missing class="nb-fig": {stripped[:60]}', line=i))
        return issues


class MissingAssetsCheck(LintCheck):
    """Error when a referenced local image file does not exist on disk."""

    name = "missing-assets"

    def run(self, path: Path, content: str) -> list[LintIssue]:
        issues = []
        in_fence = False
        for i, line in enumerate(content.splitlines(), 1):
            if re.match(r"^(?:```|~~~)", line.strip()):
                in_fence = not in_fence
            if in_fence:
                continue
            for m in re.finditer(r"!\[[^\]]*\]\(([^)\s]+)", line):
                ref = m.group(1)
                if not ref.startswith("http") and not (path.parent / ref).resolve().exists():
                    issues.append(LintIssue("error", self.name, f"missing: {ref}", line=i))
            for m in re.finditer(r'<img\b[^>]*\bsrc=["\']([^"\']+)', line, re.IGNORECASE):
                ref = m.group(1)
                if not ref.startswith("http") and not (path.parent / ref).resolve().exists():
                    issues.append(LintIssue("error", self.name, f"missing: {ref}", line=i))
        return issues


class PelicanLegacyCheck(LintCheck):
    """Error on Pelican/CodeHilite indented code blocks (    :::lang)."""

    name = "pelican-legacy"

    def run(self, _path: Path, content: str) -> list[LintIssue]:
        issues = []
        for i, line in enumerate(content.splitlines(), 1):
            if re.match(r"^    :::\w", line):
                issues.append(LintIssue("error", self.name,
                    f"CodeHilite block — convert to fenced ```: {line.strip()}", line=i))
        return issues


class MathCommandCheck(LintCheck):
    """Error on LaTeX commands unavailable in the minimal MathJax 3 config."""

    name = "math"

    def run(self, _path: Path, content: str) -> list[LintIssue]:
        issues = []
        for i, line in enumerate(content.splitlines(), 1):
            for cmd in _UNAVAILABLE_MATHJAX_COMMANDS:
                if cmd in line:
                    issues.append(LintIssue("error", self.name,
                        f"unsupported MathJax command {cmd!r}", line=i))
        return issues


# ── Registry ──────────────────────────────────────────────────────────────────

DEFAULT_CHECKS: list[LintCheck] = [
    MdformatCheck(),
    NbFigCheck(),
    MissingAssetsCheck(),
    PelicanLegacyCheck(),
    MathCommandCheck(),
]


def run_checks(
    path: Path,
    checks: list[LintCheck] | None = None,
) -> list[LintIssue]:
    """
    Run lint checks on *path*, returning all issues found.

    After any auto-fix check modifies the file the content is re-read so
    subsequent checks always see the current state.
    """
    if checks is None:
        checks = DEFAULT_CHECKS
    content = path.read_text(encoding="utf-8")
    issues: list[LintIssue] = []
    for check in checks:
        try:
            batch = check.run(path, content)
            issues.extend(batch)
            if any(i.fixed for i in batch):
                content = path.read_text(encoding="utf-8")
        except Exception as exc:
            issues.append(LintIssue("warn", check.name, f"check raised: {exc}"))
    return issues


# ── Spell check ───────────────────────────────────────────────────────────────

def _extract_prose(content: str) -> str:
    """Strip Markdown structure and return only prose text."""
    text = re.sub(r"^---\n.*?\n---\n", "", content, flags=re.DOTALL)  # frontmatter
    text = re.sub(r"```[\s\S]*?```", "", text)                         # fenced blocks
    text = re.sub(r"~~~[\s\S]*?~~~", "", text)
    text = re.sub(r"\$\$[\s\S]*?\$\$", "", text)                      # display math
    text = re.sub(r"\\\[[\s\S]*?\\\]", "", text)
    text = re.sub(r"\$[^$\n]{1,200}\$", "", text)                     # inline math
    text = re.sub(r"\\\([^)]{0,200}\\\)", "", text)
    text = re.sub(r"`[^`]+`", "", text)                                # inline code
    text = re.sub(r"<[^>]+>", "", text)                                # HTML
    text = re.sub(r"!\[[^\]]*\]\([^\)]*\)(?:\{[^\}]*\})?", "", text)  # images
    text = re.sub(r"\[([^\]]+)\]\([^\)]*\)", r"\1", text)             # links → text
    text = re.sub(r"^#+\s+", "", text, flags=re.MULTILINE)            # heading markers
    return text


_CONTRACTION_STEMS = frozenset({
    "aren", "couldn", "didn", "doesn", "hadn", "hasn", "haven",
    "isn", "mightn", "mustn", "needn", "shan", "shouldn", "wasn",
    "weren", "wouldn", "won",
})


def _is_likely_identifier(word: str) -> bool:
    """True for words that look like code identifiers rather than prose."""
    if word.isupper():
        return True
    if word[0].isupper() and any(c.isupper() for c in word[1:]):  # CamelCase
        return True
    return False


def _load_ignore() -> set[str]:
    if not SPELL_IGNORE_FILE.exists():
        return set()
    return {
        w.strip().lower()
        for w in SPELL_IGNORE_FILE.read_text(encoding="utf-8").splitlines()
        if w.strip() and not w.startswith("#")
    }


def get_unknown_words(path: Path) -> list[str]:
    """
    Return a sorted list of unrecognized prose words found in *path*.

    Strips code, math, and Markdown structure before checking. All-caps and
    CamelCase words are excluded (likely acronyms or identifiers). Words in
    .spell-ignore.txt are also excluded.
    """
    if path.suffix == ".ipynb":
        import json
        with open(path, encoding="utf-8") as f:
            nb = json.load(f)
        content = "\n".join(
            "".join(c.get("source", []))
            for c in nb.get("cells", [])
            if c.get("cell_type") == "markdown"
        )
    else:
        content = path.read_text(encoding="utf-8")
    prose = _extract_prose(content)
    raw = re.findall(r"\b[a-zA-Z]{4,}\b", prose)
    candidates = list({
        w.lower() for w in raw
        if not _is_likely_identifier(w)
        and w.lower() not in _CONTRACTION_STEMS
    })
    ignore = _load_ignore()
    candidates = [w for w in candidates if w not in ignore]
    if not candidates:
        return []
    spell = SpellChecker()
    return sorted(spell.unknown(candidates))
