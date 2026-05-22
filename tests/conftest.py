"""Shared pytest fixtures for mkprof tests."""

import shutil
from pathlib import Path

import pytest


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixture_nb(tmp_path):
    """Copy a fixture notebook to tmp_path and return a factory."""
    def _copy(name: str) -> Path:
        src = FIXTURES_DIR / name
        dst = tmp_path / name
        shutil.copy2(src, dst)
        return dst
    return _copy


@pytest.fixture
def docs_dir(tmp_path):
    """A minimal docs directory with an assets/ subdirectory."""
    assets = tmp_path / "docs" / "assets"
    assets.mkdir(parents=True)
    return tmp_path / "docs"


@pytest.fixture
def minimal_mkdocs_yml(tmp_path):
    """Write a minimal mkdocs.yml and return its path."""
    content = """\
site_name: Test Site
plugins:
  - blog:
      blog_dir: blog
      authors_file: authors.yml
"""
    p = tmp_path / "mkdocs.yml"
    p.write_text(content, encoding="utf-8")
    (tmp_path / "docs").mkdir()
    return p
