"""Integration tests: parse + render pipeline produces valid Markdown."""

import json

import yaml

from mkprof.notebook.jupyter import parse
from mkprof.notebook import render


def test_render_produces_markdown_file(fixture_nb, docs_dir):
    nb = fixture_nb("simple.ipynb")
    post = parse(nb, docs_dir)
    out_md, _ = render(post, nb, docs_dir)

    assert out_md.exists()
    assert out_md.suffix == ".md"
    content = out_md.read_text(encoding="utf-8")

    # Frontmatter block
    assert content.startswith("---\n")
    fm_end = content.index("---\n", 4)
    fm = yaml.safe_load(content[4:fm_end])
    assert fm["title"] == "A Simple Test Post"

    # Notebook download link
    assert "simple.ipynb" in content
    assert "download=" in content


def test_render_copies_notebook_to_assets(fixture_nb, docs_dir):
    nb = fixture_nb("simple.ipynb")
    post = parse(nb, docs_dir)
    render(post, nb, docs_dir)

    asset_copy = docs_dir / "assets" / "notebooks" / "simple.ipynb"
    assert asset_copy.exists()


def test_render_includes_code_output(fixture_nb, docs_dir):
    nb = fixture_nb("simple.ipynb")
    post = parse(nb, docs_dir)
    out_md, _ = render(post, nb, docs_dir)
    content = out_md.read_text(encoding="utf-8")
    assert "hello world" in content


def test_render_html_img_converted(fixture_nb, docs_dir):
    nb = fixture_nb("html_img.ipynb")
    # Create the asset file so no warning fires
    (docs_dir / "assets" / "diagram.svg").write_text("<svg/>", encoding="utf-8")
    (docs_dir / "assets" / "logo.png").write_bytes(b"\x89PNG")
    post = parse(nb, docs_dir)
    out_md, _ = render(post, nb, docs_dir)
    content = out_md.read_text(encoding="utf-8")

    # HTML img should have been converted to markdown syntax
    assert "<img" not in content
    assert "diagram.svg" in content
    # nb-fig class should be present
    assert ".nb-fig" in content
    # External image should still be in markdown form, untouched path
    assert "https://example.com/img.png" in content


def test_render_excerpt_marker(fixture_nb, docs_dir):
    nb = fixture_nb("simple.ipynb")
    post = parse(nb, docs_dir)
    out_md, _ = render(post, nb, docs_dir)
    content = out_md.read_text(encoding="utf-8")
    assert "<!-- more -->" in content


def test_render_with_code_image_output(tmp_path, docs_dir):
    # Minimal 1×1 transparent PNG
    png_b64 = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQ"
        "DwADhQGAWjR9awAAAABJRU5ErkJggg=="
    )
    nb_data = {
        "nbformat": 4, "nbformat_minor": 5,
        "metadata": {},
        "cells": [
            {"cell_type": "raw", "metadata": {}, "source": "title: Image Post\ndate: 2025-04-01\n"},
            {"cell_type": "markdown", "metadata": {}, "source": "# Image Post\n\nContent here.\n"},
            {
                "cell_type": "code", "execution_count": 1, "metadata": {},
                "source": "plot()",
                "outputs": [{
                    "output_type": "display_data",
                    "data": {"image/png": png_b64},
                    "metadata": {}
                }]
            }
        ]
    }
    nb = tmp_path / "image_post.ipynb"
    nb.write_text(json.dumps(nb_data), encoding="utf-8")

    post = parse(nb, docs_dir)
    out_md, images = render(post, nb, docs_dir)

    assert len(images) == 1
    assert images[0].exists()
    content = out_md.read_text(encoding="utf-8")
    assert "fig_000.png" in content
