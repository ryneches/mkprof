"""
mkprof.notebook — converts parsed NotebookPost objects to blog Markdown.

Usage:
    from mkprof.notebook.jupyter import parse
    from mkprof.notebook import render

    post = parse(nb_path, docs_dir)
    out_md, images = render(post, nb_path, docs_dir)
"""

import os
import shutil
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader

from .models import NotebookPost

_env = Environment(
    loader=FileSystemLoader(str(Path(__file__).parent)),
    trim_blocks=True,
    lstrip_blocks=True,
    keep_trailing_newline=True,
)
_template = _env.get_template("template.md.j2")


def render(post: NotebookPost, nb_path: Path, docs_dir: Path) -> tuple[Path, list[Path]]:
    """
    Render a NotebookPost to a Markdown file and copy the notebook asset.

    Writes <nb_path>.md and copies the notebook to
    <docs_dir>/assets/notebooks/<nb_filename> for the download link.

    Returns (output_md_path, list_of_image_paths).
    """
    frontmatter = yaml.dump(post.meta, default_flow_style=False, allow_unicode=True)

    nb_assets_dir = docs_dir / "assets" / "notebooks"
    nb_assets_dir.mkdir(parents=True, exist_ok=True)

    # Relative path from the output .md to the notebooks asset dir, for the
    # download link in the template (markdown links are correctly adjusted by
    # MkDocs regardless of blog post URL depth).
    md_dir = nb_path.parent
    nb_asset_path = Path(os.path.relpath(nb_assets_dir, md_dir)).as_posix()

    markdown = _template.render(
        post=post,
        frontmatter=frontmatter,
        nb_asset_path=nb_asset_path,
    )

    out_path = nb_path.with_suffix(".md")
    out_path.write_text(markdown, encoding="utf-8")

    shutil.copy2(nb_path, nb_assets_dir / nb_path.name)

    return out_path, post.images
