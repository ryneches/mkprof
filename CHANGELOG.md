# Changelog

All notable changes to mkprof will be documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
mkprof uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - unreleased

### Added
- Jupyter notebook parser: extracts metadata, code cells, markdown cells,
  figures (PNG, JPEG, GIF, SVG), and error outputs
- Markdown renderer: converts parsed notebooks to mkdocs-material-compatible
  Markdown via a Jinja2 template
- Asset path rewriter: normalises local asset references in notebook markdown
  cells; converts HTML `<img>` tags to markdown image syntax so mkdocs handles
  path depth correctly for blog posts
- Mtime-based skip: notebooks whose generated `.md` is already up to date are
  not re-converted
- Markdown linter: mdformat auto-formatting, MathJax compatibility checks,
  spell check with per-project ignore list
- Plain Markdown metadata utilities: read/write/hint frontmatter for `.md`
  posts authored outside notebooks, including Obsidian compatibility
- Marimo parser stub (not yet implemented)
- Interactive TUI (`mkprof`, `mkprof serve`, `mkprof convert`): prompts for
  missing blog frontmatter with content-aware pre-filling, lint display,
  draft management
- `mkprof init`: scaffolds a new mkdocs-material site with blog plugin and
  mkprof pre-configured
- Config resolution: derives posts directory, docs directory, and default
  author from existing `mkdocs.yml`; merges `extra.mkprof` overrides
- Example `hooks.py` for nav injection and recent-post summaries
