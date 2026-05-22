"""
notebook/markdown.py — Markdown file frontmatter utilities.

Handles reading, writing, and hinting blog metadata for plain .md files,
including files authored in Obsidian (wikilinks, embeds, callouts, comments).
"""

import re
from pathlib import Path

import yaml


# ── Inline content cleaning ───────────────────────────────────────────────────

def _clean_inline(text: str) -> str:
    """Strip Obsidian/Markdown inline markup, returning plain text."""
    text = re.sub(r'%%.*?%%', '', text, flags=re.DOTALL)       # Obsidian comments
    text = re.sub(r'!\[\[[^\]]*\]\]', '', text)                 # Obsidian embeds
    text = re.sub(r'\[\[([^\]|]+)\|([^\]]+)\]\]', r'\2', text) # [[page|display]] → display
    text = re.sub(r'\[\[([^\]]+)\]\]', r'\1', text)             # [[page]] → page
    text = re.sub(r'\[([^\]]+)\]\([^\)]*\)', r'\1', text)       # [text](url) → text
    text = re.sub(r'\*{1,3}(.+?)\*{1,3}', r'\1', text)         # bold/italic *
    text = re.sub(r'_{1,3}(.+?)_{1,3}', r'\1', text)           # bold/italic _
    text = re.sub(r'`[^`]+`', '', text)                         # inline code
    text = re.sub(r'(?<!\w)#[\w/-]+', '', text)                 # Obsidian inline #tags
    return re.sub(r'\s+', ' ', text).strip()


# ── Content peeking ───────────────────────────────────────────────────────────

def peek_content(text: str) -> tuple[str | None, str | None]:
    """
    Extract (title, description) from markdown text.

    Finds the first ATX (# Title) or setext (underline ===) H1, then collects
    the first prose paragraph after it.  Obsidian quirks handled: wikilinks,
    embeds (![[...]]), callouts (> [!type]), and comment blocks (%%...%%).
    Returns (None, None) if no H1 is found.
    """
    lines = text.split('\n')

    # Skip YAML frontmatter block
    start = 0
    if lines and lines[0].strip() == '---':
        for i in range(1, len(lines)):
            if lines[i].strip() in ('---', '...'):
                start = i + 1
                break

    # Find first H1
    title: str | None = None
    title_idx = -1
    in_code = False
    for i, line in enumerate(lines[start:], start):
        stripped = line.strip()
        if re.match(r'^(?:```|~~~)', stripped):
            in_code = not in_code
        if in_code:
            continue
        if re.match(r'^#\s', line):                             # ATX: # Title
            title = _clean_inline(re.sub(r'^#+\s+', '', line))
            title_idx = i
            break
        if re.match(r'^=+\s*$', stripped) and i > start and lines[i - 1].strip():
            title = _clean_inline(lines[i - 1].strip())        # setext: underlined
            title_idx = i
            break

    if title_idx < 0:
        return None, None

    # Collect first prose paragraph after title
    in_para = False
    para_lines: list[str] = []
    in_code = False
    in_comment = False

    for line in lines[title_idx + 1:]:
        stripped = line.strip()

        # Obsidian %%block comments%%
        opens = stripped.count('%%')
        if opens:
            if opens % 2 == 1:
                in_comment = not in_comment
            continue
        if in_comment:
            continue

        if re.match(r'^(?:```|~~~)', stripped):
            in_code = not in_code
            if in_para:
                break
            continue
        if in_code:
            continue

        if not stripped:
            if in_para:
                break
            continue

        if re.match(r'^!\[\[', stripped):           # Obsidian embed — skip
            continue
        if re.match(r'^>\s*\[!', stripped):         # Obsidian callout — skip
            if in_para:
                break
            continue
        if stripped.startswith('>'):                # blockquote — end para
            if in_para:
                break
            continue
        if stripped.startswith('#'):                # subheading — end section
            if in_para:
                break
            continue
        if re.match(r'^[-*_]{3,}\s*$', stripped):  # horizontal rule
            if in_para:
                break
            continue
        if re.match(r'^[-*+]\s', stripped) or re.match(r'^\d+[.)]\s', stripped):
            if in_para:                             # list — end para
                break
            continue

        in_para = True
        para_lines.append(stripped)

    description = _clean_inline(' '.join(para_lines)) if para_lines else None
    return title, description


# ── Frontmatter I/O ───────────────────────────────────────────────────────────

def _read_frontmatter(text: str) -> tuple[dict, int]:
    """
    Parse YAML frontmatter from markdown text.
    Returns (meta_dict, body_start_line_index).
    meta_dict is {} if no valid frontmatter is found.
    """
    lines = text.split('\n')
    if not lines or lines[0].strip() != '---':
        return {}, 0
    for i in range(1, len(lines)):
        if lines[i].strip() in ('---', '...'):
            try:
                meta = yaml.safe_load('\n'.join(lines[1:i]))
                if isinstance(meta, dict):
                    return {k.lower(): v for k, v in meta.items()}, i + 1
            except yaml.YAMLError:
                pass
            return {}, i + 1
    return {}, 0


def extract_metadata(md_path: Path) -> dict | None:
    """Return blog frontmatter if it contains both title and date, else None."""
    text = md_path.read_text(encoding='utf-8')
    meta, _ = _read_frontmatter(text)
    if 'title' in meta and 'date' in meta:
        return meta
    return None


def peek_hints(md_path: Path) -> dict:
    """
    Return pre-fill hints for the metadata modal.

    Merges any partial frontmatter already in the file with title/description
    extracted from the document content.
    """
    text = md_path.read_text(encoding='utf-8')
    hints, _ = _read_frontmatter(text)

    if 'title' not in hints or 'description' not in hints:
        title, desc = peek_content(text)
        if 'title' not in hints and title:
            hints['title'] = title
        if 'description' not in hints and desc:
            hints['description'] = desc

    return hints


def write_metadata(md_path: Path, meta: dict) -> None:
    """
    Write blog frontmatter to a markdown file.

    Merges with any existing frontmatter (preserving Obsidian-specific fields
    like aliases), then rewrites the file with the combined header.
    """
    text = md_path.read_text(encoding='utf-8')
    existing, body_start = _read_frontmatter(text)

    merged = {**existing, **meta}
    yaml_str = yaml.dump(merged, default_flow_style=False, allow_unicode=True).rstrip('\n')
    new_front = f'---\n{yaml_str}\n---\n'

    body_lines = text.split('\n')[body_start:]
    body = '\n'.join(body_lines)
    if body and not body.startswith('\n'):
        body = '\n' + body

    md_path.write_text(new_front + body, encoding='utf-8')
