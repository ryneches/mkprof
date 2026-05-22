# Changelog

All notable changes to mkprof will be documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
mkprof uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- Documentation site is live at [mkprof.vort.org](https://mkprof.vort.org)
- `docs/design.md` added: documents the opinionated layout choices with
  references to Pirolli & Card's information foraging theory, Dave Winer's
  river of news, Frank Chimero's *The Web's Grain*, and Nielsen's
  recognition-over-recall heuristic; also frames mkprof as a tool for
  academic research blogs in the tradition of the researcher's workstation
- Init templates moved from Python string literals to real files under
  `src/mkprof/templates/`; `init_cmd.py` loads them at runtime via
  `importlib.resources` — templates now have syntax highlighting and can be
  edited without escaping
- Nav injection (`hooks.py` / `on_nav`): posts are now injected directly as
  children of the Blog section rather than wrapped in a collapsible "Posts"
  sub-section, so they are visible without an extra click
- Blog section is open by default via `docs/javascripts/blog_nav.js`, which
  sets the Material accordion checkbox for the Blog nav item on every page
  load (including `navigation.instant` transitions); `navigation.expand`
  (which expands every section) is not used
- `docs/stylesheets/extra.css` expanded: ships stubs for `.nb-fig`,
  `.nb-photo`, tables, DataFrames, code blocks, and the `recent-posts`
  admonition — structural layout rules with color placeholders so users
  start with a working skeleton and make their own color decisions
- `mkprof init` now generates a complete, working site rather than a
  bare-bones stub:
  - Full `hooks.py` with nav injection and `<!-- RECENT_POSTS -->` support
  - `mkdocs.yml` includes `pymdownx.emoji` (required for Material icons in
    notebook download links), `pymdownx.arithmatex` + MathJax, dark/light
    palette toggle, social cards plugin, and tags plugin; style-only choices
    are marked with brief `# Style:` comments
  - `docs/stylesheets/extra.css` with CSS stubs for figures, photos, tables,
    DataFrames, code blocks, and the recent-posts admonition
  - `docs/javascripts/mathjax.js` MathJax configuration
  - `docs/tags.md` for the tags plugin
  - `docs/index.md` includes the `<!-- RECENT_POSTS -->` placeholder

### Fixed
- `.nb-fig` styling now applies to figures in non-blog pages (e.g. pages
  under Projects) and hand-authored Markdown files, not only notebook posts:
  - `on_page_markdown` hook now injects `{ .nb-fig }` at build time on any
    standalone image (sole content of its paragraph) that has non-empty alt
    text and no existing attr_list block; authors who explicitly set
    `{ .nb-photo }` or other attrs are not overridden
  - `_rewrite_asset_paths` in `jupyter.py` now applies `.nb-fig` to all
    local images with alt text in notebook markdown cells, not only those
    whose path was rewritten — fixing the class being silently dropped for
    notebooks outside `docs/blog/posts/`

### Added
- Author pick-list in the metadata TUI: the authors field is replaced with a
  `SelectionList` loaded from `authors.yml`, with previously-set authors
  pre-ticked; falls back to free-text input when no `authors.yml` is present
- `MkprofConfig.authors`: config resolution now exposes the full slug → display
  name map from `authors.yml`, not just the single-author default

### Fixed
- `mkprof convert` no longer launches the Textual TUI; it runs headlessly,
  logs to stdout, and exits non-zero on conversion errors — safe for CI
- `authors.yml` format corrected to use the Material blog plugin's required
  `authors:` wrapper key; `mkprof init` generates the same correct format
- `config.resolve()` now unwraps the `authors:` envelope before inferring
  `default_author`, so single-author sites are detected correctly
- `authors.yml` entries now include a required `avatar` field; `mkprof init`
  defaults to `https://github.com/{slug}.png`
- `config.resolve()` no longer crashes on `mkdocs.yml` files that contain
  `!!python/name:` YAML tags (used by `pymdownx.emoji`); a custom loader
  silently ignores Python-object tags that are not needed for config parsing

## [0.1.0] - unreleased

### Added
- Jupyter notebook parser: extracts metadata, code cells, markdown cells,
  figures (PNG, JPEG, GIF, SVG), and error outputs
- Markdown renderer: converts parsed notebooks to mkdocs-material-compatible
  Markdown via a Jinja2 template
- Asset path rewriter: normalizes local asset references in notebook markdown
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
