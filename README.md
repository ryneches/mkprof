# mkprof

A companion tool for [mkdocs-material](https://squidfunk.github.io/mkdocs-material/)
that converts Jupyter notebooks into blog posts.

If mkdocs is a table saw, mkprof is the crosscut sled — it makes a specific
set of operations safer, more repeatable, and faster. It handles the awkward
parts of the notebook-to-blog workflow so you can focus on writing.

Why is it called mkprof? Well, who makes the thing that makes the docs? In
any event, this is a tool for making a personal site for a me, and I'm a
professor, so... look, I had to name it *something*.

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
- Ships an example `hooks.py` for nav injection and recent-post summaries

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
mkprof              convert notebooks + prompt to build or serve
mkprof serve        convert notebooks + start mkdocs dev server
mkprof convert      convert notebooks only, skip mkdocs
mkprof init [DIR]   scaffold a new site (default: current directory)
```

## How it fits with mkdocs

mkprof is intentionally not a mkdocs plugin. It runs as a separate step
before `mkdocs build`, generating standard Markdown that mkdocs-material
handles natively. This keeps the conversion logic decoupled from mkdocs
internals and makes it straightforward to adapt when
[Zensical](https://www.zensical.com/) matures.

## License

MIT
