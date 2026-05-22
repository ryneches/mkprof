"""
mkprof.config — resolve configuration from mkdocs.yml and extra.mkprof overrides.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class MkprofConfig:
    docs_dir: Path
    posts_dir: Path
    drafts_dir: Path
    default_author: str
    site_name: str
    mkdocs_yml: Path


def resolve(mkdocs_yml: Path | None = None) -> MkprofConfig:
    """
    Derive mkprof configuration from mkdocs.yml.

    Priority (lowest to highest):
      1. Sensible defaults
      2. Values derived from the blog plugin's own config in mkdocs.yml
      3. Single-author inference from authors.yml
      4. Explicit overrides in the extra.mkprof section of mkdocs.yml
    """
    if mkdocs_yml is None:
        mkdocs_yml = Path("mkdocs.yml")
    if not mkdocs_yml.exists():
        raise FileNotFoundError(
            f"mkdocs.yml not found at {mkdocs_yml.resolve()}. "
            "Run 'mkprof init' to scaffold a new site."
        )

    root = mkdocs_yml.parent
    raw = yaml.safe_load(mkdocs_yml.read_text(encoding="utf-8")) or {}

    # ── docs_dir ──────────────────────────────────────────────────────────────
    docs_dir = root / raw.get("docs_dir", "docs")

    # ── site_name ─────────────────────────────────────────────────────────────
    site_name = str(raw.get("site_name", "mkprof Blog Builder"))

    # ── blog plugin config ────────────────────────────────────────────────────
    blog_dir = "blog"
    authors_file_rel = "authors.yml"
    for entry in raw.get("plugins", []):
        # plugins list entries can be bare strings or {name: config} dicts
        if isinstance(entry, dict) and "blog" in entry:
            blog_cfg = entry["blog"] or {}
            blog_dir = blog_cfg.get("blog_dir", blog_dir)
            authors_file_rel = blog_cfg.get("authors_file", authors_file_rel)
            break

    posts_dir = docs_dir / blog_dir / "posts"

    # ── default_author: infer from authors.yml if there is exactly one ────────
    default_author = ""
    authors_path = docs_dir / authors_file_rel
    if authors_path.exists():
        try:
            authors_data = yaml.safe_load(authors_path.read_text(encoding="utf-8")) or {}
            if isinstance(authors_data, dict) and len(authors_data) == 1:
                default_author = next(iter(authors_data))
        except yaml.YAMLError:
            pass

    # ── drafts_dir ────────────────────────────────────────────────────────────
    drafts_dir = root / "drafts"

    # ── extra.mkprof overrides ────────────────────────────────────────────────
    overrides = (raw.get("extra") or {}).get("mkprof") or {}
    if "posts_dir" in overrides:
        posts_dir = root / overrides["posts_dir"]
    if "drafts_dir" in overrides:
        drafts_dir = root / overrides["drafts_dir"]
    if "default_author" in overrides:
        default_author = str(overrides["default_author"])

    return MkprofConfig(
        docs_dir=docs_dir.resolve(),
        posts_dir=posts_dir.resolve(),
        drafts_dir=drafts_dir.resolve(),
        default_author=default_author,
        site_name=site_name,
        mkdocs_yml=mkdocs_yml.resolve(),
    )
