"""
notebook/markdown.py — Markdown file frontmatter utilities.

Handles reading, writing, and hinting blog metadata for plain .md files,
including files authored in Obsidian (wikilinks, embeds, callouts, comments).
"""

import re
from pathlib import Path

import yaml


# ── Code-span protection ──────────────────────────────────────────────────────

def _stash_code(text: str) -> tuple[str, list[str]]:
    """Replace fenced blocks and inline code with NUL-delimited index tokens.

    Prevents Obsidian transformations from modifying code examples that
    demonstrate the syntax being transformed.  Call _unstash_code to restore.
    """
    stash: list[str] = []

    def _save(m: re.Match) -> str:
        stash.append(m.group(0))
        return f'\x00{len(stash) - 1}\x00'

    # Fenced code blocks (``` or ~~~, matching fence length)
    text = re.sub(
        r'^(`{3,}|~{3,})[^\n]*\n.*?\n\1[ \t]*$',
        _save, text, flags=re.MULTILINE | re.DOTALL,
    )
    # Inline code spans (single/double/triple backtick)
    text = re.sub(r'(`{1,3}).+?\1', _save, text)
    return text, stash


def _unstash_code(text: str, stash: list[str]) -> str:
    return re.sub(r'\x00(\d+)\x00', lambda m: stash[int(m.group(1))], text)


# ── Obsidian → MkDocs transformations ────────────────────────────────────────

# ![[file]] or ![[file|alt text]]
_OBSIDIAN_EMBED = re.compile(r'!\[\[([^|\]\n]+?)(?:\|([^\]\n]*))?\]\]')
_IMAGE_EXTS = frozenset({'.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.avif'})

# [[page]] or [[page|display]] — negative lookbehind excludes ![[...]] embeds
_WIKILINK = re.compile(r'(?<!!)\[\[([^\]|\n]+?)(?:\|([^\]\n]*))?\]\]')

_OBSIDIAN_COMMENT = re.compile(r'%%.*?%%', re.DOTALL)

_CALLOUT_HEADER = re.compile(
    r'^> \[!([A-Za-z]+)\]([+\-]?)(?:[ \t]+(.+?))?[ \t]*$'
)
_CALLOUT_TYPE_MAP: dict[str, str] = {
    'note':       'note',
    'abstract':   'abstract', 'summary':   'abstract', 'tldr':      'abstract',
    'info':       'info',     'information': 'info',
    'todo':       'note',
    'tip':        'tip',      'hint':       'tip',      'important': 'tip',
    'success':    'success',  'check':      'success',  'done':      'success',
    'question':   'question', 'help':       'question', 'faq':       'question',
    'warning':    'warning',  'caution':    'warning',  'attention': 'warning',
    'failure':    'failure',  'fail':       'failure',  'missing':   'failure',
    'danger':     'danger',   'error':      'danger',
    'bug':        'bug',
    'example':    'example',
    'quote':      'quote',    'cite':       'quote',
}


def _expand_image_embeds(
    text: str,
    rel_assets: str,
    assets_dir: Path,
) -> tuple[str, list[str]]:
    """Convert ``![[image]]`` and ``![[image|alt]]`` to standard markdown.

    Resolves filenames against docs/assets/.  Leaves non-image embeds and
    missing files unchanged; appends a warning string for each missing file.
    Converted images receive ``{ .nb-photo }``.
    """
    text, stash = _stash_code(text)
    warnings: list[str] = []

    def _replace(m: re.Match) -> str:
        filename = m.group(1).strip()
        alt = (m.group(2) or filename).strip()
        if Path(filename).suffix.lower() not in _IMAGE_EXTS:
            return m.group(0)
        if not (assets_dir / filename).exists():
            warnings.append(f'not found in docs/assets/: {filename!r}')
            return m.group(0)
        return f'![{alt}]({rel_assets}/{filename})' + '{ .nb-photo }'

    text = _OBSIDIAN_EMBED.sub(_replace, text)
    return _unstash_code(text, stash), warnings


def _strip_obsidian_comments(text: str) -> str:
    """Remove ``%%...%%`` Obsidian comments (inline and block).

    Collapses any resulting runs of three or more blank lines to two.
    Code spans and fenced blocks are left untouched.
    """
    text, stash = _stash_code(text)
    text = _OBSIDIAN_COMMENT.sub('', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return _unstash_code(text, stash)


def _rewrite_wikilinks(text: str) -> str:
    """Convert ``[[page]]`` / ``[[page|display]]`` wiki-links to plain text.

    ``[[Page Name]]`` → ``Page Name``
    ``[[page.md]]``   → ``page``       (stem, extension stripped)
    ``[[page|label]]`` → ``label``

    Image embeds (``![[...]]]``) and code spans are left untouched.
    """
    text, stash = _stash_code(text)

    def _replace(m: re.Match) -> str:
        target = m.group(1).strip()
        display = (m.group(2) or Path(target).stem).strip()
        return display

    text = _WIKILINK.sub(_replace, text)
    return _unstash_code(text, stash)


def _rewrite_callouts(text: str) -> str:
    """Convert Obsidian callouts to Material for MkDocs admonitions.

    ``> [!type] Title``    →  ``!!! type "Title"``
    ``> [!type]+ Title``   →  ``???+ type "Title"``   (foldable, open)
    ``> [!type]- Title``   →  ``??? type "Title"``    (foldable, closed)

    Known Obsidian type aliases (e.g. caution, hint, cite) are mapped to their
    Material equivalents.  Unknown types are passed through as-is.
    Fenced code blocks are left untouched.
    """
    text, stash = _stash_code(text)
    lines = text.split('\n')
    result: list[str] = []
    i = 0
    while i < len(lines):
        m = _CALLOUT_HEADER.match(lines[i])
        if m:
            raw_type = m.group(1).lower()
            admon_type = _CALLOUT_TYPE_MAP.get(raw_type, raw_type)
            fold = m.group(2)
            title = (m.group(3) or '').strip()

            prefix = '???+' if fold == '+' else '???' if fold == '-' else '!!!'
            result.append(
                f'{prefix} {admon_type} "{title}"' if title
                else f'{prefix} {admon_type}'
            )
            result.append('')   # blank line required before indented body

            i += 1
            body_lines: list[str] = []
            while i < len(lines):
                line = lines[i]
                if line == '>':
                    body_lines.append('')
                elif line.startswith('> '):
                    body_lines.append('    ' + line[2:])
                else:
                    break
                i += 1

            result.extend(body_lines)
            if result[-1] != '':   # ensure blank line after admonition body
                result.append('')
        else:
            result.append(lines[i])
            i += 1

    return _unstash_code('\n'.join(result), stash)


def rewrite_obsidian(md_path: Path, docs_dir: Path) -> list[str]:
    """Apply all Obsidian → MkDocs transformations to a markdown file in-place.

    Transformations applied to the body (YAML frontmatter is preserved):
      - ``![[image]]`` embeds resolved against docs/assets/ → standard markdown
      - ``%%...%%`` comments stripped
      - ``[[wiki-links]]`` reduced to display text
      - ``> [!type]`` callouts converted to Material admonitions

    Writes the file only when at least one change is made.  Returns a list of
    warning strings (e.g. image embeds whose file was not found in assets/).
    """
    text = md_path.read_text(encoding='utf-8')

    # Preserve YAML frontmatter — operate only on the body
    _, body_start = _read_frontmatter(text)
    all_lines = text.split('\n')
    if body_start > 0:
        front = '\n'.join(all_lines[:body_start])
        body = '\n'.join(all_lines[body_start:])
    else:
        front = ''
        body = text

    # Relative path from this file's directory to docs/assets/
    try:
        rel_parts = [p for p in md_path.parent.relative_to(docs_dir).parts if p != '.']
    except ValueError:
        rel_parts = []
    rel_assets = '/'.join(['..'] * len(rel_parts) + ['assets']) if rel_parts else 'assets'
    assets_dir = docs_dir / 'assets'

    warnings: list[str] = []
    body, embed_warnings = _expand_image_embeds(body, rel_assets, assets_dir)
    warnings.extend(embed_warnings)
    body = _strip_obsidian_comments(body)
    body = _rewrite_wikilinks(body)
    body = _rewrite_callouts(body)

    new_text = front + '\n' + body if front else body
    if new_text != text:
        md_path.write_text(new_text, encoding='utf-8')
    return warnings


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
