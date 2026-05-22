---
title: Getting started with mkprof
date: 2026-05-22
authors:
  - ryneches
tags:
  - guide
description: >
  How to install mkprof, scaffold a new site, and write your first
  Jupyter notebook blog post.
---

mkprof is a companion tool for MkDocs Material that converts Jupyter notebooks
into blog posts. This post walks you through getting set up from scratch.

<!-- more -->

## Installation

Install mkprof with pip:

```bash
pip install mkprof
```

You'll also need mkdocs-material if you don't have it:

```bash
pip install mkdocs-material
```

## Scaffold a new site

The `mkprof init` command creates a minimal site structure:

```bash
mkprof init my-blog
cd my-blog
```

This writes:

```
my-blog/
  mkdocs.yml          ← MkDocs configuration
  hooks.py            ← MkDocs event hooks (empty, ready to customise)
  .gitignore
  docs/
    index.md
    blog/
      index.md
      posts/          ← put your notebooks here
    authors.yml       ← author metadata
```

## Add your first notebook

Create a Jupyter notebook in `docs/blog/posts/` and add a raw metadata cell
as the **first cell**:

```yaml
title: My First Post
date: 2026-01-15
authors:
  - your-slug
tags:
  - hello world
```

Write the rest of your post in the remaining cells as normal.

If the metadata cell is missing or incomplete, mkprof will prompt you when
you next run `mkprof` or `mkprof serve`. The authors field shows a
selectable list drawn from `docs/authors.yml`, so you can tick the right
names rather than typing slugs by hand. Multiple authors can be selected
for a single post.

## Convert and serve (local development)

Run mkprof from the project root:

```bash
mkprof serve
```

mkprof will:

1. Discover notebooks in `docs/blog/posts/`
2. Prompt you to fill in any missing metadata through an interactive dialog
3. Convert each notebook to a Markdown file
4. Start `mkdocs serve` so you can preview the site at `http://127.0.0.1:8000`

`mkprof` (no subcommand) does the same but asks whether to build or serve
after conversion.

## CI and automated builds

For CI pipelines, use `mkprof convert` instead. It is fully non-interactive:
no TUI, no prompts — it logs to stdout and exits non-zero if any conversion
fails. Notebooks without metadata are skipped with a warning rather than
halting the build.

```yaml
# GitHub Actions example
- run: mkprof convert && mkdocs build
```

Any notebook that was skipped due to missing metadata will simply be absent
from the built site. Run `mkprof` locally to fill in the metadata and commit
the updated notebook before the next CI run.

## Assets

Images and other assets referenced from notebook markdown cells should be
placed in `docs/assets/`. Reference them as `assets/filename.ext` in your
notebook — mkprof rewrites the paths correctly regardless of where MkDocs
publishes the post.

HTML `<img>` tags whose `src` points to a local asset are automatically
converted to Markdown image syntax, which ensures MkDocs handles the path
depth correctly for blog posts.
