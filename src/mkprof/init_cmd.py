"""
mkprof.init_cmd — scaffold a new mkprof/mkdocs-material site.
"""

import sys
from pathlib import Path


_MKDOCS_YML = """\
site_name: {site_name}

docs_dir: docs

# Prevent raw notebooks and Jupyter checkpoints from being included in the build.
exclude_docs: |
  blog/posts/*.ipynb
  **/.ipynb_checkpoints/

hooks:
  - hooks.py

theme:
  name: material
  features:
    - content.code.copy
    - navigation.indexes
    - navigation.instant
    - navigation.footer
    - navigation.top
    - search.suggest
    - search.highlight
    - toc.follow

plugins:
  - search
  - blog:
      blog_dir: blog
      authors: true
      authors_file: authors.yml
      post_excerpt: optional
      post_excerpt_separator: <!-- more -->

markdown_extensions:
  - admonition
  - attr_list
  - footnotes
  - toc:
      permalink: true
  - pymdownx.highlight
  - pymdownx.superfences
"""

_AUTHORS_YML = """\
authors:
  {slug}:
    name: {name}
    description: {name}
"""

_HOOKS_PY = '''\
"""
hooks.py — MkDocs event hooks for this site.

See: https://www.mkdocs.org/user-guide/configuration/#hooks
"""

# Add site-level hooks here.  For example:
#
# def on_page_markdown(markdown, *, page, config, files):
#     return markdown
'''

_DOCS_INDEX_MD = """\
---
title: Home
---

# Welcome

This site is built with [MkDocs Material](https://squidfunk.github.io/mkdocs-material/).

See the [Blog](blog/index.md) for posts.
"""

_BLOG_INDEX_MD = """\
# Blog
"""

_GITIGNORE = """\
site/
__pycache__/
*.pyc
.ipynb_checkpoints/
"""


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

    # ── Stage files to write ──────────────────────────────────────────────────
    files: list[tuple[Path, str]] = [
        (target / "mkdocs.yml", _MKDOCS_YML.format(site_name=site_name)),
        (target / "hooks.py", _HOOKS_PY),
        (target / ".gitignore", _GITIGNORE),
        (target / "docs" / "index.md", _DOCS_INDEX_MD),
        (target / "docs" / "blog" / "index.md", _BLOG_INDEX_MD),
    ]

    if author_slug:
        files.append((
            target / "docs" / "authors.yml",
            _AUTHORS_YML.format(
                slug=author_slug,
                name=author_name or author_slug,
            ),
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
