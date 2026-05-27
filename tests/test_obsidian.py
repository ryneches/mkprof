"""Tests for Obsidian → MkDocs markdown transformations."""

import pytest
from pathlib import Path

from mkprof.notebook.markdown import (
    _expand_image_embeds,
    _rewrite_callouts,
    _rewrite_wikilinks,
    _strip_obsidian_comments,
    rewrite_obsidian,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

@pytest.fixture
def assets_dir(tmp_path):
    d = tmp_path / "assets"
    d.mkdir()
    return d


@pytest.fixture
def site(tmp_path):
    """Minimal site: docs/assets/ + docs/blog/posts/.  Returns (make_post, docs_dir)."""
    docs = tmp_path / "docs"
    (docs / "assets").mkdir(parents=True)
    (docs / "blog" / "posts").mkdir(parents=True)

    def _make(content: str, name: str = "article.md") -> Path:
        p = docs / "blog" / "posts" / name
        p.write_text(content, encoding="utf-8")
        return p

    return _make, docs


# ── Comment stripping ─────────────────────────────────────────────────────────

def test_strip_inline_comment():
    assert _strip_obsidian_comments("hello %%secret%% world") == "hello  world"


def test_strip_block_comment():
    result = _strip_obsidian_comments("before\n%%\nmulti\nline\n%%\nafter")
    assert "multi" not in result
    assert "before" in result
    assert "after" in result


def test_strip_comment_collapses_blank_lines():
    # Removing a block comment shouldn't leave more than one blank line.
    result = _strip_obsidian_comments("a\n\n%%block%%\n\nb")
    assert "\n\n\n" not in result


def test_comment_preserved_in_fenced_block():
    text = "```\n%%this should stay%%\n```"
    assert _strip_obsidian_comments(text) == text


def test_comment_preserved_in_inline_code():
    text = "use `%%comment%%` syntax in Obsidian"
    assert _strip_obsidian_comments(text) == text


def test_multiple_inline_comments():
    result = _strip_obsidian_comments("a %%x%% b %%y%% c")
    assert result == "a  b  c"


# ── Wiki-link rewriting ───────────────────────────────────────────────────────

def test_wikilink_bare():
    assert _rewrite_wikilinks("see [[My Note]]") == "see My Note"


def test_wikilink_with_display_text():
    assert _rewrite_wikilinks("see [[My Note|this note]]") == "see this note"


def test_wikilink_strips_extension():
    assert _rewrite_wikilinks("[[report.md]]") == "report"


def test_wikilink_nested_path_uses_stem():
    assert _rewrite_wikilinks("[[folder/note.md]]") == "note"


def test_wikilink_image_embed_untouched():
    text = "![[photo.png]]"
    assert _rewrite_wikilinks(text) == text


def test_wikilink_preserved_in_fenced_block():
    text = "```\n[[wikilink]]\n```"
    assert _rewrite_wikilinks(text) == text


def test_wikilink_preserved_in_inline_code():
    text = "use `[[PageName]]` to link"
    assert _rewrite_wikilinks(text) == text


def test_multiple_wikilinks():
    result = _rewrite_wikilinks("[[A]] and [[B|bee]]")
    assert result == "A and bee"


# ── Callout rewriting ─────────────────────────────────────────────────────────

def test_callout_basic():
    result = _rewrite_callouts("> [!note] My Note\n> Content here")
    assert '!!! note "My Note"' in result
    assert "    Content here" in result


def test_callout_no_title():
    result = _rewrite_callouts("> [!warning]\n> Watch out")
    assert "!!! warning" in result
    assert "    Watch out" in result


def test_callout_foldable_open():
    result = _rewrite_callouts("> [!tip]+ Expand me\n> Tip content")
    assert '???+ tip "Expand me"' in result
    assert "    Tip content" in result


def test_callout_foldable_closed():
    result = _rewrite_callouts("> [!danger]- Hide this\n> Danger content")
    assert '??? danger "Hide this"' in result
    assert "    Danger content" in result


def test_callout_type_aliases_warning():
    assert "!!! warning" in _rewrite_callouts("> [!caution]\n> body")
    assert "!!! warning" in _rewrite_callouts("> [!attention]\n> body")


def test_callout_type_aliases_tip():
    assert "!!! tip" in _rewrite_callouts("> [!hint]\n> body")
    assert "!!! tip" in _rewrite_callouts("> [!important]\n> body")


def test_callout_type_aliases_abstract():
    assert "!!! abstract" in _rewrite_callouts("> [!summary]\n> body")
    assert "!!! abstract" in _rewrite_callouts("> [!tldr]\n> body")


def test_callout_type_case_insensitive():
    assert "!!! note" in _rewrite_callouts("> [!NOTE] Title\n> body")
    assert "!!! warning" in _rewrite_callouts("> [!Warning]\n> body")


def test_callout_unknown_type_passed_through():
    result = _rewrite_callouts("> [!custom] My Type\n> body")
    assert "!!! custom" in result


def test_callout_multi_line_body():
    text = "> [!info] Title\n> Line one\n> Line two\n> Line three"
    result = _rewrite_callouts(text)
    assert "    Line one" in result
    assert "    Line two" in result
    assert "    Line three" in result


def test_callout_empty_body():
    result = _rewrite_callouts("> [!note] Empty")
    assert '!!! note "Empty"' in result


def test_callout_body_with_blank_lines():
    text = "> [!note] Title\n> First\n>\n> Second"
    result = _rewrite_callouts(text)
    assert "    First" in result
    assert "    Second" in result


def test_regular_blockquote_not_modified():
    text = "> This is a regular quote\n> continuing"
    assert _rewrite_callouts(text) == text


def test_callout_does_not_affect_surrounding_text():
    text = "Before\n\n> [!note] Title\n> body\n\nAfter"
    result = _rewrite_callouts(text)
    assert "Before" in result
    assert "After" in result
    assert "> [!note]" not in result


def test_callout_preserved_in_fenced_block():
    text = "```\n> [!note] Title\n> body\n```"
    assert _rewrite_callouts(text) == text


# ── Image embed expansion ─────────────────────────────────────────────────────

def test_image_embed_found(assets_dir):
    (assets_dir / "photo.jpg").touch()
    text, warnings = _expand_image_embeds("![[photo.jpg]]", "../../assets", assets_dir)
    assert "![photo.jpg](../../assets/photo.jpg)" in text
    assert "{ .nb-photo }" in text
    assert warnings == []


def test_image_embed_with_alt(assets_dir):
    (assets_dir / "fig.png").touch()
    text, _ = _expand_image_embeds("![[fig.png|My Figure]]", "../../assets", assets_dir)
    assert "![My Figure](../../assets/fig.png)" in text


def test_image_embed_missing_warns(assets_dir):
    _, warnings = _expand_image_embeds("![[missing.png]]", "../../assets", assets_dir)
    assert len(warnings) == 1
    assert "missing.png" in warnings[0]


def test_image_embed_missing_leaves_original(assets_dir):
    text, _ = _expand_image_embeds("![[missing.png]]", "../../assets", assets_dir)
    assert "![[missing.png]]" in text


def test_non_image_embed_unchanged(assets_dir):
    text = "![[document.pdf]]"
    out, warnings = _expand_image_embeds(text, "../../assets", assets_dir)
    assert out == text
    assert warnings == []


def test_image_embed_all_extensions(assets_dir):
    for ext in ("png", "jpg", "jpeg", "gif", "svg", "webp", "avif"):
        fname = f"img.{ext}"
        (assets_dir / fname).touch()
        text, w = _expand_image_embeds(f"![[{fname}]]", "assets", assets_dir)
        assert f"![{fname}](assets/{fname})" in text
        assert w == []


def test_image_embed_preserved_in_fenced_block(assets_dir):
    (assets_dir / "photo.png").touch()
    text = "```\n![[photo.png]]\n```"
    out, warnings = _expand_image_embeds(text, "assets", assets_dir)
    assert out == text
    assert warnings == []


def test_multiple_embeds_partial_missing(assets_dir):
    (assets_dir / "found.png").touch()
    text, warnings = _expand_image_embeds(
        "![[found.png]] and ![[missing.png]]", "assets", assets_dir
    )
    assert "![found.png](assets/found.png)" in text
    assert "![[missing.png]]" in text
    assert len(warnings) == 1


# ── rewrite_obsidian integration ──────────────────────────────────────────────

def test_integration_image_resolved(site):
    make, docs = site
    (docs / "assets" / "hero.png").touch()
    md = make("---\ntitle: Test\n---\n\n![[hero.png]]\n")
    rewrite_obsidian(md, docs)
    content = md.read_text()
    assert "![[hero.png]]" not in content
    assert "../../assets/hero.png" in content
    assert "{ .nb-photo }" in content


def test_integration_relative_path_depth(site):
    """Posts at docs/blog/posts/ are 2 levels deep → ../../assets."""
    make, docs = site
    (docs / "assets" / "deep.png").touch()
    md = make("![[deep.png]]\n")
    rewrite_obsidian(md, docs)
    assert "../../assets/deep.png" in md.read_text()


def test_integration_frontmatter_preserved(site):
    make, docs = site
    md = make("---\ntitle: My Post\ndate: 2026-01-01\n---\n\n%%remove me%%\n")
    rewrite_obsidian(md, docs)
    content = md.read_text()
    assert "title: My Post" in content
    assert "date: 2026-01-01" in content
    assert "%%remove me%%" not in content


def test_integration_wikilinks_stripped(site):
    make, docs = site
    md = make("See [[Other Post|this post]] for details.\n")
    rewrite_obsidian(md, docs)
    content = md.read_text()
    assert "this post" in content
    assert "[[" not in content


def test_integration_callout_converted(site):
    make, docs = site
    md = make("> [!warning] Heads up\n> Be careful.\n")
    rewrite_obsidian(md, docs)
    content = md.read_text()
    assert '!!! warning "Heads up"' in content
    assert "> [!warning]" not in content


def test_integration_missing_image_warns(site):
    make, docs = site
    md = make("![[no-such-file.png]]\n")
    warnings = rewrite_obsidian(md, docs)
    assert any("no-such-file.png" in w for w in warnings)


def test_integration_no_obsidian_syntax_not_rewritten(site):
    make, docs = site
    original = "# Plain markdown\n\nNo Obsidian syntax here.\n"
    md = make(original)
    rewrite_obsidian(md, docs)
    assert md.read_text() == original


def test_integration_all_features_combined(site):
    make, docs = site
    (docs / "assets" / "chart.png").touch()
    content = (
        "---\ntitle: Combined\n---\n\n"
        "%%draft note%%\n\n"
        "See [[Related Article|this]].\n\n"
        "![[chart.png|Sales Chart]]\n\n"
        "> [!tip] Pro tip\n> Use mkprof.\n"
    )
    md = make(content)
    rewrite_obsidian(md, docs)
    result = md.read_text()

    assert "%%draft note%%" not in result
    assert "[[Related Article" not in result
    assert "this" in result
    assert "![[chart.png" not in result
    assert "Sales Chart" in result
    assert "{ .nb-photo }" in result
    assert '!!! tip "Pro tip"' in result
    assert "title: Combined" in result   # frontmatter intact
