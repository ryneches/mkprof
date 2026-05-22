---
title: mkprof
---

# mkprof

**mkprof** is a companion tool for [MkDocs Material](https://squidfunk.github.io/mkdocs-material/)
that converts Jupyter notebooks into blog posts.

## What it does

- Discovers `.ipynb` files in your blog's posts directory
- Prompts for any missing YAML frontmatter through an interactive TUI
- Converts notebooks to Markdown, extracting figures and preserving code outputs
- Rewrites local asset references so paths resolve correctly after MkDocs builds the site
- Runs `mkdocs build` or `mkdocs serve` once conversion is complete

## Quick start

Install from PyPI:

```bash
pip install mkprof
```

Scaffold a new site:

```bash
mkprof init my-blog
cd my-blog
mkprof serve
```

Or add it to an existing site by running `mkprof` from the directory that
contains your `mkdocs.yml`.

## Commands

| Command | Description |
|---------|-------------|
| `mkprof` | Convert notebooks, then prompt to build or serve |
| `mkprof serve` | Convert notebooks and start `mkdocs serve` |
| `mkprof build` | Convert notebooks and run `mkdocs build` |
| `mkprof convert` | Convert notebooks only; skip running mkdocs |
| `mkprof init [DIR]` | Scaffold a new mkprof/mkdocs-material site |

## Configuration

mkprof reads its configuration from your existing `mkdocs.yml`.
Blog post and drafts directories are inferred from the `blog` plugin settings.
Override them with an `extra.mkprof` section:

```yaml
extra:
  mkprof:
    posts_dir: docs/blog/posts   # default: derived from blog plugin
    drafts_dir: drafts           # default: drafts/ at project root
    default_author: your-slug    # default: inferred if authors.yml has one entry
```

## Blog

See the [Blog](blog/index.md) for release notes and announcements.
