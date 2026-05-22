"""Tests for mkprof.notebook.jupyter."""

import datetime
import json

import pytest

from mkprof.notebook.jupyter import (
    extract_metadata,
    parse,
    peek_hints,
    write_metadata_to_notebook,
)
from mkprof.notebook.models import CodeCell, ExcerptMarker, MarkdownCell


def test_extract_metadata_valid(fixture_nb):
    nb = fixture_nb("simple.ipynb")
    meta = extract_metadata(nb)
    assert meta is not None
    assert meta["title"] == "A Simple Test Post"
    assert meta["date"] == datetime.date(2025, 3, 1)


def test_extract_metadata_missing(fixture_nb):
    nb = fixture_nb("missing_meta.ipynb")
    assert extract_metadata(nb) is None


def test_peek_hints_finds_h1(fixture_nb):
    nb = fixture_nb("simple.ipynb")
    hints = peek_hints(nb)
    assert hints.get("title") == "A Simple Test Post"


def test_peek_hints_missing_meta_notebook(fixture_nb):
    nb = fixture_nb("missing_meta.ipynb")
    hints = peek_hints(nb)
    assert hints.get("title") == "Post Without Metadata"


def test_parse_basic(fixture_nb, docs_dir):
    nb = fixture_nb("simple.ipynb")
    post = parse(nb, docs_dir)
    assert post.meta["title"] == "A Simple Test Post"
    assert post.nb_filename == "simple.ipynb"

    markdown_cells = [c for c in post.cells if isinstance(c, MarkdownCell)]
    code_cells = [c for c in post.cells if isinstance(c, CodeCell)]
    assert len(markdown_cells) == 1
    assert len(code_cells) == 1
    assert "hello world" in code_cells[0].outputs[0].content


def test_parse_inserts_excerpt_marker(fixture_nb, docs_dir):
    nb = fixture_nb("simple.ipynb")
    post = parse(nb, docs_dir)
    kinds = [c.kind for c in post.cells]
    assert "excerpt_marker" in kinds


def test_parse_no_duplicate_excerpt_when_explicit(tmp_path, docs_dir):
    nb_data = {
        "nbformat": 4, "nbformat_minor": 5,
        "metadata": {},
        "cells": [
            {"cell_type": "raw", "metadata": {}, "source": "title: T\ndate: 2025-01-01\n"},
            {"cell_type": "markdown", "metadata": {}, "source": "# T\n\nIntro.\n\n<!-- more -->\n\nBody.\n"},
        ]
    }
    nb = tmp_path / "explicit_more.ipynb"
    nb.write_text(json.dumps(nb_data), encoding="utf-8")
    post = parse(nb, docs_dir)
    excerpt_count = sum(1 for c in post.cells if isinstance(c, ExcerptMarker))
    assert excerpt_count == 0  # explicit <!-- more --> in source, no synthetic marker


def test_parse_raises_for_missing_metadata(fixture_nb, docs_dir):
    nb = fixture_nb("missing_meta.ipynb")
    with pytest.raises(ValueError, match="No blog metadata"):
        parse(nb, docs_dir)


def test_write_metadata_to_notebook(fixture_nb):
    nb = fixture_nb("missing_meta.ipynb")
    meta = {"title": "New Title", "date": datetime.date(2025, 6, 1)}
    write_metadata_to_notebook(nb, meta)
    result = extract_metadata(nb)
    assert result is not None
    assert result["title"] == "New Title"
