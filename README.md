# mkprof

[![CI](https://github.com/ryneches/mkprof/actions/workflows/ci.yml/badge.svg)](https://github.com/ryneches/mkprof/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/mkprof)](https://pypi.org/project/mkprof/)
[![PyPI downloads](https://img.shields.io/pypi/dm/mkprof)](https://pypi.org/project/mkprof/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![commits since release](https://img.shields.io/github/commits-since/ryneches/mkprof/latest)](https://github.com/ryneches/mkprof/releases)
[![Mastodon Follow](https://img.shields.io/mastodon/follow/109294614904147843?domain=https%3A%2F%2Fecoevo.social)](https://ecoevo.social/@ryneches)

A companion tool for [mkdocs-material](https://squidfunk.github.io/mkdocs-material/)
for building and running a blog that natively supports Jupyter notebooks
as articles.

If you think of of mkdocs as something like a table saw, then mkprof is a
table saw jig, like a cross-cut sled. It is a doohicky you add to a general
purpose tool that makes a specific set of operations safer, more repeatable,
and faster.

Why is it called mkprof? Well, professors mentor doctoral candidates, and if
mkdocs makes docs, then... look, naming things is hard and I was tired.

![mkprof metadata TUI — adding frontmatter to a notebook post](docs/assets/demo.gif)

## What it does

- Converts `.ipynb` notebooks in your posts directory to mkdocs-compatible
  Markdown, extracting figures, handling asset paths, and adding a notebook
  download link
- Provides an interactive TUI that prompts for any missing blog frontmatter
  (title, date, description, tags, authors) with content-aware pre-filling
- Lints and auto-formats Markdown posts (mdformat, spell check, MathJax
  compatibility checks)
- Skips conversion when the generated `.md` is already newer than its source
  notebook
- `mkprof init` scaffolds a complete, opinionated site: `hooks.py` with nav
  injection and recent-posts support, MathJax, dark/light palette toggle,
  tags, Blog section open by default in the sidebar (via a small script that
  sets Material's accordion checkbox, not `navigation.expand`), and a CSS file with
  stubs for figures, photographs, tables, DataFrames, code blocks, and the
  recent-posts admonition — structural rules with color placeholders so you
  start with a working layout and make your own color decisions

mkprof is a pre-processor: it runs before `mkdocs build`, transforming
notebooks into Markdown that mkdocs-material already knows how to handle.

## Requirements

- Python 3.11+
- [mkdocs-material](https://squidfunk.github.io/mkdocs-material/) with the
  built-in `blog` plugin enabled

## Installation

```bash
pip install mkprof
```

## Quick start

### Fresh site

```bash
mkprof init mysite
cd mysite
mkprof serve
```

`mkprof init` scaffolds a ready-to-use mkdocs-material site with the blog
plugin and mkprof pre-configured. Drop `.ipynb` notebooks into
`docs/blog/posts/` and run `mkprof` to convert and build.

### Existing mkdocs-material site

```bash
pip install mkprof
# run from your site root (the directory containing mkdocs.yml)
mkprof
```

mkprof reads your existing `mkdocs.yml` to locate `docs_dir` and your blog
posts directory. No extra config file is required for a standard layout.

For non-standard layouts or per-site overrides, add an `extra.mkprof` section
to your `mkdocs.yml`:

```yaml
extra:
  mkprof:
    posts_dir: docs/content/posts   # default: derived from blog plugin config
    drafts_dir: _drafts             # default: drafts
    default_author: yourslug        # default: inferred from authors.yml
```

## Commands

```
mkprof              TUI: convert notebooks + prompt to build or serve
mkprof serve        TUI: convert notebooks + start mkdocs dev server
mkprof build        TUI: convert notebooks + run mkdocs build
mkprof convert      headless: convert notebooks only (CI-safe, no prompts)
mkprof init [DIR]   scaffold a new site (default: current directory)
```

`mkprof`, `mkprof serve`, and `mkprof build` launch a Textual TUI that
prompts interactively for any missing blog frontmatter and lets you move
incomplete posts to drafts.

`mkprof convert` is non-interactive: it logs to stdout, skips notebooks
that are missing metadata without prompting, and exits non-zero on
conversion errors. Use it in CI:

```yaml
- run: mkprof convert && mkdocs build
```

## How it fits with mkdocs

mkprof is intentionally not a mkdocs plugin. It runs as a separate step
before `mkdocs build`, generating standard Markdown that mkdocs-material
handles natively. This keeps the conversion logic decoupled from mkdocs
internals and makes it straightforward to adapt when
[Zensical](https://www.zensical.com/) matures.

## License

MIT
