"""mkprof — companion tool for mkdocs-material notebook blogs."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("mkprof")
except PackageNotFoundError:
    __version__ = "unknown"
