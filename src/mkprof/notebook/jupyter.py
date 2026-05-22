"""
mkprof.notebook.jupyter — Jupyter (.ipynb) notebook parser.

Extracts blog metadata and cell content from a notebook file and returns
a NotebookPost.  No markdown is produced here; all formatting lives in
notebook/template.md.j2 and is applied by notebook.render().
"""

import base64
import datetime
import json
import os
import re
from pathlib import Path

import yaml

from .models import (
    CodeCell,
    ErrorOutput,
    ExcerptMarker,
    ImageOutput,
    MarkdownCell,
    NotebookPost,
    TextOutput,
)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _cell_source(cell: dict) -> str:
    src = cell.get("source", [])
    return "".join(src) if isinstance(src, list) else src


def _parse_output(
    output: dict,
    img_dir: Path,
    counter: list[int],
    images: list[Path],
) -> TextOutput | ImageOutput | ErrorOutput | None:
    otype = output.get("output_type", "")

    if otype == "stream":
        text = "".join(output.get("text", []))
        if text.strip():
            return TextOutput(content=text.rstrip())

    elif otype in ("display_data", "execute_result"):
        data = output.get("data", {})

        # Priority order: prefer richer/vector formats first.
        # SVG data is raw XML text; all other image types are base64-encoded.
        _IMAGE_TYPES = [
            ("image/svg+xml", "svg", False),
            ("image/png",     "png", True),
            ("image/jpeg",    "jpg", True),
            ("image/gif",     "gif", True),
        ]
        for mime, ext, is_b64 in _IMAGE_TYPES:
            if mime not in data:
                continue
            n = counter[0]
            counter[0] += 1
            fname = f"fig_{n:03d}.{ext}"
            img_dir.mkdir(parents=True, exist_ok=True)
            raw = data[mime]
            if isinstance(raw, list):
                raw = "".join(raw)
            img_path = img_dir / fname
            if is_b64:
                img_path.write_bytes(base64.b64decode(raw))
            else:
                img_path.write_text(raw, encoding="utf-8")
            images.append(img_path)
            return ImageOutput(path=f"{img_dir.name}/{fname}", index=n)

        if "text/plain" in data:
            text = "".join(data["text/plain"])
            if text.strip():
                return TextOutput(content=text.rstrip())

    elif otype == "error":
        return ErrorOutput(
            name=output.get("ename", "Error"),
            value=output.get("evalue", ""),
        )

    return None


def _rewrite_asset_paths(
    content: str,
    nb_path: Path,
    assets_dir: Path,
    warnings_out: list[str],
) -> str:
    """Rewrite local asset references in a Markdown cell.

    HTML <img> tags whose src resolves to an asset are converted to markdown
    image syntax so MkDocs' standard URL rewriting handles path depth
    correctly for blog posts.  All other asset references use paths relative
    to the source .md file, which MkDocs also handles natively.
    """
    md_dir = nb_path.parent
    try:
        rel_prefix = Path(os.path.relpath(assets_dir, md_dir)).as_posix()
    except ValueError:
        return content  # different drives on Windows

    def _rewrite(raw_path: str) -> str:
        """Return a relative asset path, or raw_path if not a local asset."""
        if raw_path.startswith(("http://", "https://", "//", "#", "mailto:", "/")):
            return raw_path
        normalised = re.sub(r"^\./+", "", raw_path)
        if normalised.startswith("assets/"):
            rel_file = normalised[len("assets/"):]
            if not (assets_dir / rel_file).exists():
                warnings_out.append(f"file not found in docs/assets/: {raw_path!r}")
            return f"{rel_prefix}/{rel_file}"
        if "/" not in normalised and (assets_dir / normalised).exists():
            return f"{rel_prefix}/{normalised}"
        return raw_path

    # Markdown image / link: ![alt](path) or [text](path) with optional title
    def _sub_md(m: re.Match) -> str:
        bang, alt, path, rest = m.group(1), m.group(2), m.group(3), m.group(4) or ""
        new_path = _rewrite(path)
        result = f"{bang}[{alt}]({new_path}{rest}"
        if bang == "!" and new_path != path:
            result += "{ .nb-fig }"
        return result

    content = re.sub(
        r'(!?)\[([^\]]*)\]\(([^)\s"\'<>]+)((?:\s+"[^"]*")?\))',
        _sub_md,
        content,
    )

    # HTML <img> tags — convert to markdown image syntax when src is an asset.
    # Markdown images are rewritten correctly by MkDocs regardless of the blog
    # plugin's output depth; raw HTML src= attributes are not.
    def _img_to_md(m: re.Match) -> str:
        tag = m.group(0)
        src_m = re.search(r'\bsrc=(["\'])([^"\']+)\1', tag)
        if not src_m:
            return tag
        new_src = _rewrite(src_m.group(2))
        if new_src == src_m.group(2):
            return tag  # src is not an asset — leave raw HTML unchanged

        alt_m = re.search(r'\balt=(["\'])([^"\']*)\1', tag)
        alt = alt_m.group(2) if alt_m else ""

        # Gather remaining attributes for the attr_list block.
        attrs = [".nb-fig"]
        for am in re.finditer(r'\b(\w[\w-]*)=(?:(["\'])([^"\']*)\2|(\w+))', tag):
            name = am.group(1)
            val = am.group(3) if am.group(2) else am.group(4)
            if name in ("src", "alt"):
                continue
            if name == "class":
                attrs.extend(f".{c}" for c in val.split() if c != "nb-fig")
            elif name == "id":
                attrs.append(f"#{val}")
            else:
                attrs.append(f'{name}="{val}"')

        return f'![{alt}]({new_src}){{ {" ".join(attrs)} }}'

    content = re.sub(r"<img\b[^>]*/?>", _img_to_md, content)

    # Other HTML src= / href= attributes (anchors, etc.) — rewrite if asset.
    def _sub_html(m: re.Match) -> str:
        attr, q, path = m.group(1), m.group(2), m.group(3)
        return f"{attr}={q}{_rewrite(path)}{q}"

    content = re.sub(r'\b(src|href)=(["\'])([^"\']+)\2', _sub_html, content)

    return content


# ── Public API ────────────────────────────────────────────────────────────────

def peek_hints(nb_path: Path) -> dict:
    """
    Extract title/description hints from notebook content cells.

    Scans markdown cells (skipping a leading metadata cell if present) for
    the first H1 heading and the paragraph that follows it.
    """
    from .markdown import peek_content

    with open(nb_path, encoding='utf-8') as f:
        nb = json.load(f)

    cells = nb.get('cells', [])
    start = 0
    if cells and cells[0].get('cell_type') in ('raw', 'markdown'):
        try:
            if isinstance(yaml.safe_load(_cell_source(cells[0])), dict):
                start = 1
        except yaml.YAMLError:
            pass

    for cell in cells[start:]:
        if cell.get('cell_type') != 'markdown':
            continue
        src = _cell_source(cell)
        if not src.strip():
            continue
        title, desc = peek_content(src)
        if title:
            hints: dict = {'title': title}
            if desc:
                hints['description'] = desc
            return hints

    return {}


def extract_metadata(nb_path: Path) -> dict | None:
    """Return blog metadata dict from the first notebook cell, or None."""
    with open(nb_path, encoding="utf-8") as f:
        nb = json.load(f)
    cells = nb.get("cells", [])
    if not cells:
        return None
    first = cells[0]
    if first.get("cell_type") not in ("raw", "markdown"):
        return None
    source = _cell_source(first)
    try:
        meta = yaml.safe_load(source)
        if isinstance(meta, dict):
            meta = {k.lower(): v for k, v in meta.items()}
            if "title" in meta and "date" in meta:
                return meta
    except yaml.YAMLError:
        pass
    return None


def write_metadata_to_notebook(nb_path: Path, meta: dict) -> None:
    """Prepend (or replace) a raw YAML metadata cell in the notebook."""
    with open(nb_path, encoding="utf-8") as f:
        nb = json.load(f)

    yaml_src = yaml.dump(meta, default_flow_style=False, allow_unicode=True).rstrip("\n")
    new_cell: dict = {"cell_type": "raw", "metadata": {}, "source": yaml_src}

    cells = nb.get("cells", [])
    if cells and cells[0].get("cell_type") in ("raw", "markdown"):
        try:
            probe = yaml.safe_load(_cell_source(cells[0]))
            if isinstance(probe, dict):
                cells[0] = new_cell
            else:
                cells.insert(0, new_cell)
        except yaml.YAMLError:
            cells.insert(0, new_cell)
    else:
        cells.insert(0, new_cell)

    nb["cells"] = cells
    with open(nb_path, "w", encoding="utf-8") as f:
        json.dump(nb, f, indent=1, ensure_ascii=False)


def parse(nb_path: Path, docs_dir: Path) -> NotebookPost:
    """Parse a Jupyter notebook into a NotebookPost ready for rendering."""
    with open(nb_path, encoding="utf-8") as f:
        nb = json.load(f)

    meta = extract_metadata(nb_path)
    if meta is None:
        raise ValueError(f"No blog metadata found in {nb_path.name}")

    # Normalise date to datetime.date so yaml.dump serialises it as YYYY-MM-DD.
    d = meta.get("date")
    if isinstance(d, datetime.datetime):
        meta["date"] = d.date()
    elif isinstance(d, str):
        try:
            meta["date"] = datetime.date.fromisoformat(d[:10])
        except ValueError:
            pass

    img_dir = nb_path.parent / f"{nb_path.stem}_files"
    img_counter: list[int] = [0]
    images: list[Path] = []
    asset_warnings: list[str] = []
    assets_dir = docs_dir / "assets"

    content_cells = nb.get("cells", [])[1:]  # skip metadata cell

    has_explicit_more = any(
        "<!-- more -->" in _cell_source(c)
        for c in content_cells
        if c.get("cell_type") == "markdown"
    )

    cells = []
    excerpt_inserted = False

    for raw_cell in content_cells:
        ctype = raw_cell.get("cell_type", "")
        src = _cell_source(raw_cell)

        if ctype == "markdown" and src.strip():
            src = _rewrite_asset_paths(src, nb_path, assets_dir, asset_warnings)
            cells.append(MarkdownCell(content=src))
            if not has_explicit_more and not excerpt_inserted and len(src.strip()) > 50:
                cells.append(ExcerptMarker())
                excerpt_inserted = True

        elif ctype == "code" and src.strip():
            outputs = []
            for out in raw_cell.get("outputs", []):
                parsed = _parse_output(out, img_dir, img_counter, images)
                if parsed is not None:
                    outputs.append(parsed)
            cells.append(CodeCell(source=src, outputs=outputs))

        # raw cells after the first are skipped

    return NotebookPost(
        meta=meta,
        cells=cells,
        nb_filename=nb_path.name,
        images=images,
        asset_warnings=asset_warnings,
    )
