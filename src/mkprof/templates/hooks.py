"""
hooks.py — MkDocs build hooks.

on_nav:             Injects individual blog posts as Link items directly in
                    the Blog nav section, running after the blog plugin (at
                    priority -100) so that post URLs are final before the
                    links are written.

on_page_markdown:   Replaces <!-- RECENT_POSTS --> in any page with a
                    summary of the N most recent blog posts.
"""

import datetime
import re
from pathlib import Path

import yaml
from mkdocs.plugins import event_priority
from mkdocs.structure.nav import Link


# ── Shared helpers ────────────────────────────────────────────────────────────

def _to_date(d) -> datetime.date:
    if isinstance(d, datetime.datetime):
        return d.date()
    if isinstance(d, datetime.date):
        return d
    return datetime.date.fromisoformat(str(d)[:10])


def _load_posts(config) -> list[dict]:
    """Return all blog posts as dicts, sorted newest-first."""
    docs_dir = Path(config["docs_dir"])
    posts_dir = docs_dir / "blog" / "posts"

    posts = []
    for md_path in sorted(posts_dir.glob("*.md")):
        text = md_path.read_text(encoding="utf-8")
        m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
        if not m:
            continue
        try:
            meta = yaml.safe_load(m.group(1))
        except yaml.YAMLError:
            continue
        if not isinstance(meta, dict):
            continue
        title = meta.get("title")
        post_date = meta.get("date")
        if not title or not post_date:
            continue
        posts.append({
            "title": str(title),
            "date": post_date,
            "description": str(meta.get("description", "")),
            "path": f"blog/posts/{md_path.name}",
            "body": text[m.end():].strip(),
        })

    posts.sort(key=lambda p: _to_date(p["date"]), reverse=True)
    return posts


def _excerpt(body: str, max_chars: int = 280) -> str:
    """Extract the first substantive paragraph from markdown body."""
    body = body.split("<!-- more -->")[0]
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith(("#", "```", "![", "|", "---", ">")):
            continue
        line = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", line)
        line = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", line)
        line = re.sub(r"[*_`]{1,2}([^*_`]+)[*_`]{1,2}", r"\1", line)
        line = line.strip()
        if len(line) > 60:
            return line[:max_chars] + ("…" if len(line) > max_chars else "")
    return ""


# ── Hook: nav injection ───────────────────────────────────────────────────────

@event_priority(-100)
def on_nav(nav, config, files, **kwargs):
    """Inject blog posts as Link nav items directly inside the Blog Section.

    Runs after the blog plugin so post URLs are final.  Links are inserted
    directly as children of the Blog section — not wrapped in a sub-section —
    so they are visible without expanding a nested group.  We use Link items
    rather than Page items so the blog plugin's NOT_IN_NAV flag doesn't
    suppress them.
    """
    posts = _load_posts(config)
    if not posts:
        return

    links = []
    for post in posts:
        f = files.get_file_from_path(post["path"])
        if f is None:
            continue
        url = "/" + f.dest_uri.removesuffix("index.html")
        links.append(Link(post["title"], url))

    if not links:
        return

    # Must match the nav section title in mkdocs.yml.
    blog_section = None
    for item in nav.items:
        if hasattr(item, "children") and item.children is not None and item.title == "Blog":
            blog_section = item
            break

    if blog_section is None:
        return

    blog_idx = next(
        (i for i, child in enumerate(blog_section.children)
         if hasattr(child, "file") and child.file and child.file.src_path == "blog/index.md"),
        None,
    )
    if blog_idx is None:
        return

    for i, link in enumerate(links):
        link.parent = blog_section
        blog_section.children.insert(blog_idx + 1 + i, link)


# ── Hook: recent posts injection ──────────────────────────────────────────────

RECENT_POSTS_PLACEHOLDER = "<!-- RECENT_POSTS -->"
RECENT_POSTS_COUNT = 5  # Style: number of recent posts shown by the placeholder.


def on_page_markdown(markdown, page, config, files, **kwargs):
    if RECENT_POSTS_PLACEHOLDER not in markdown:
        return markdown

    posts = _load_posts(config)[:RECENT_POSTS_COUNT]

    inner = []
    for p in posts:
        date_str = _to_date(p["date"]).strftime("%-d %B %Y")
        inner.append(f"**[{p['title']}]({p['path']})**")
        inner.append(f"*{date_str}*")
        inner.append("")
        blurb = p["description"] or _excerpt(p["body"])
        if blurb:
            inner.append(blurb)
            inner.append("")

    inner.append("[All posts →](blog/index.md)")

    indented = "\n".join(f"    {line}" if line else "" for line in inner)
    # Style: "recent-posts" is a custom admonition type — style it in extra.css.
    block = f'!!! recent-posts "Recent Posts"\n\n{indented}'

    return markdown.replace(RECENT_POSTS_PLACEHOLDER, block)
