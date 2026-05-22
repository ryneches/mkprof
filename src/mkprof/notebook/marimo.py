"""
notebook/marimo.py — Marimo (.py) notebook parser.

Marimo notebooks store no cell outputs — they must be executed to capture
rendered results.  The planned approach is:

  1.  Run ``marimo export html <notebook.py> --output <tmp.html>`` to execute
      the notebook and capture all outputs, including static snapshots of
      mo.ui.* widgets.
  2.  Parse the resulting HTML with BeautifulSoup to extract cell sources and
      their rendered outputs (text, images, widget snapshots).
  3.  Map each cell to the appropriate model type:
        - mo.md(...)        → MarkdownCell
        - plain code        → CodeCell
        - mo.ui.*           → WidgetCell  (uses the static HTML snapshot)
        - plots / DataFrames → CodeCell with ImageOutput / TextOutput
  4.  Return a NotebookPost with the same structure as the Jupyter parser.

The WidgetCell description field can be populated from the mo.ui constructor
call parsed out of the cell source (e.g. "slider(0–10)").
"""

from pathlib import Path

from .models import NotebookPost


def parse(nb_path: Path) -> NotebookPost:
    raise NotImplementedError(
        "Marimo parser not yet implemented — see notebook/marimo.py for the plan."
    )
