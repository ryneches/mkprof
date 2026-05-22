"""Tests for asset path rewriting in notebook markdown cells."""

import pytest

from mkprof.notebook.jupyter import _rewrite_asset_paths


@pytest.fixture
def rewrite(tmp_path):
    """Return a helper that calls _rewrite_asset_paths with a tmp docs/assets dir."""
    assets_dir = tmp_path / "docs" / "assets"
    assets_dir.mkdir(parents=True)
    nb_path = tmp_path / "docs" / "blog" / "posts" / "test.ipynb"
    nb_path.parent.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []

    def _call(content: str) -> tuple[str, list[str]]:
        warnings.clear()
        result = _rewrite_asset_paths(content, nb_path, assets_dir, warnings)
        return result, list(warnings)

    return _call


def test_markdown_image_asset_is_rewritten(rewrite):
    out, _ = rewrite("![alt](assets/figure.png)")
    assert "../../assets/figure.png" in out
    assert "{ .nb-fig }" in out


def test_markdown_image_external_unchanged(rewrite):
    url = "https://example.com/img.png"
    out, _ = rewrite(f"![alt]({url})")
    assert url in out
    assert ".nb-fig" not in out


def test_html_img_converted_to_markdown(rewrite):
    out, _ = rewrite('<img src="assets/diagram.svg" alt="A diagram" />')
    assert out.startswith("![A diagram]")
    assert "../../assets/diagram.svg" in out
    assert ".nb-fig" in out


def test_html_img_external_unchanged(rewrite):
    tag = '<img src="https://example.com/img.png" alt="ext" />'
    out, _ = rewrite(tag)
    assert out == tag


def test_html_img_preserves_width_attribute(rewrite):
    out, _ = rewrite('<img src="assets/fig.png" alt="f" width="500" />')
    assert 'width="500"' in out
    assert ".nb-fig" in out


def test_html_img_preserves_class_attribute(rewrite):
    out, _ = rewrite('<img src="assets/fig.png" alt="f" class="center big" />')
    assert ".center" in out
    assert ".big" in out
    # nb-fig should not be duplicated from the class attr
    assert out.count("nb-fig") == 1


def test_missing_asset_warns(rewrite):
    # assets/nonexistent.png does NOT exist in the tmp assets dir
    _, warnings = rewrite("![alt](assets/nonexistent.png)")
    assert any("nonexistent.png" in w for w in warnings)


def test_markdown_link_to_asset_is_rewritten(rewrite):
    out, _ = rewrite("[Download](assets/data.csv)")
    assert "../../assets/data.csv" in out


def test_absolute_url_not_rewritten(rewrite):
    content = "![alt](/assets/figure.png)"
    out, _ = rewrite(content)
    assert out == content
