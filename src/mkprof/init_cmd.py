"""
mkprof.init_cmd — scaffold a new mkprof/mkdocs-material site.
"""

import sys
from importlib.resources import files as _pkg_files
from pathlib import Path

_TEMPLATES = _pkg_files("mkprof") / "templates"


def _tpl(name: str) -> str:
    return (_TEMPLATES / name).read_text(encoding="utf-8")


def _prompt(label: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        value = input(f"{label}{suffix}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(0)
    return value or default


def run_init(target: Path) -> None:
    target = target.resolve()

    if (target / "mkdocs.yml").exists():
        print(f"mkprof: {target / 'mkdocs.yml'} already exists — aborting.")
        sys.exit(1)

    print(f"Scaffolding a new mkprof site in {target}/\n")

    default_name = target.name.replace("-", " ").replace("_", " ").title()
    site_name = _prompt("Site name", default_name)

    author_name = _prompt("Author name (optional, press Enter to skip)", "")
    if author_name:
        default_slug = author_name.lower().replace(" ", "-")
        author_slug = _prompt("Author slug (used in authors.yml)", default_slug)
    else:
        author_slug = ""

    # ── Create directory tree ─────────────────────────────────────────────────
    (target / "docs" / "blog" / "posts").mkdir(parents=True, exist_ok=True)
    (target / "docs" / "stylesheets").mkdir(parents=True, exist_ok=True)
    (target / "docs" / "javascripts").mkdir(parents=True, exist_ok=True)

    # ── Stage files to write ──────────────────────────────────────────────────
    files: list[tuple[Path, str]] = [
        (target / "mkdocs.yml",                           _tpl("mkdocs.yml").format(site_name=site_name)),
        (target / "hooks.py",                             _tpl("hooks.py")),
        (target / ".gitignore",                           _tpl("gitignore")),
        (target / "docs" / "index.md",                   _tpl("index.md")),
        (target / "docs" / "tags.md",                    _tpl("tags.md")),
        (target / "docs" / "blog" / "index.md",          _tpl("blog_index.md")),
        (target / "docs" / "stylesheets" / "extra.css",  _tpl("extra.css")),
        (target / "docs" / "javascripts" / "mathjax.js", _tpl("mathjax.js")),
        (target / "docs" / "javascripts" / "blog_nav.js", _tpl("blog_nav.js")),
    ]

    if author_slug:
        files.append((
            target / "docs" / "authors.yml",
            _tpl("authors.yml").format(slug=author_slug, name=author_name or author_slug),
        ))

    for path, content in files:
        rel = path.relative_to(target)
        if path.exists():
            print(f"  skip  {rel}  (already exists)")
        else:
            path.write_text(content, encoding="utf-8")
            print(f"  write {rel}")

    print(f"\nDone.  Next steps:")
    print(f"  cd {target}")
    print(f"  mkprof serve")
