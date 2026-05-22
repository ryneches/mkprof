"""Tests for mkprof.config.resolve()."""

import pytest

from mkprof.config import resolve


def test_resolve_basic(minimal_mkdocs_yml, tmp_path):
    cfg = resolve(minimal_mkdocs_yml)
    assert cfg.site_name == "Test Site"
    assert cfg.docs_dir == (tmp_path / "docs").resolve()
    assert cfg.posts_dir == (tmp_path / "docs" / "blog" / "posts").resolve()
    assert cfg.drafts_dir == (tmp_path / "drafts").resolve()


def test_resolve_missing_yml(tmp_path):
    with pytest.raises(FileNotFoundError, match="mkdocs.yml not found"):
        resolve(tmp_path / "nonexistent.yml")


def test_resolve_default_author_from_single_author(tmp_path):
    yml = tmp_path / "mkdocs.yml"
    yml.write_text(
        "site_name: Test\nplugins:\n  - blog:\n      authors_file: authors.yml\n",
        encoding="utf-8",
    )
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "authors.yml").write_text(
        "authors:\n  alice:\n    name: Alice\n    description: Author\n",
        encoding="utf-8",
    )
    cfg = resolve(yml)
    assert cfg.default_author == "alice"


def test_resolve_no_default_author_when_multiple(tmp_path):
    yml = tmp_path / "mkdocs.yml"
    yml.write_text(
        "site_name: Test\nplugins:\n  - blog:\n      authors_file: authors.yml\n",
        encoding="utf-8",
    )
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "authors.yml").write_text(
        "authors:\n  alice:\n    name: Alice\n  bob:\n    name: Bob\n",
        encoding="utf-8",
    )
    cfg = resolve(yml)
    assert cfg.default_author == ""


def test_resolve_extra_mkprof_overrides(tmp_path):
    yml = tmp_path / "mkdocs.yml"
    yml.write_text(
        "site_name: Test\nextra:\n  mkprof:\n    posts_dir: custom/posts\n    default_author: custom-author\n",
        encoding="utf-8",
    )
    (tmp_path / "docs").mkdir()
    cfg = resolve(yml)
    assert cfg.posts_dir == (tmp_path / "custom" / "posts").resolve()
    assert cfg.default_author == "custom-author"


def test_resolve_authors_map(tmp_path):
    yml = tmp_path / "mkdocs.yml"
    yml.write_text(
        "site_name: Test\nplugins:\n  - blog:\n      authors_file: authors.yml\n",
        encoding="utf-8",
    )
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "authors.yml").write_text(
        "authors:\n  alice:\n    name: Alice Smith\n  bob:\n    name: Bob Jones\n",
        encoding="utf-8",
    )
    cfg = resolve(yml)
    assert cfg.authors == {"alice": "Alice Smith", "bob": "Bob Jones"}
    assert cfg.default_author == ""  # multiple authors → no default


def test_resolve_bare_blog_plugin_string(tmp_path):
    yml = tmp_path / "mkdocs.yml"
    yml.write_text(
        "site_name: Test\nplugins:\n  - search\n  - blog\n",
        encoding="utf-8",
    )
    (tmp_path / "docs").mkdir()
    cfg = resolve(yml)
    assert cfg.posts_dir == (tmp_path / "docs" / "blog" / "posts").resolve()
