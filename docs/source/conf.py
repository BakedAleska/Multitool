"""Sphinx configuration for the Multitool documentation.

Docs are built from docstrings via ``sphinx.ext.autodoc``. Run
``sphinx-apidoc`` and ``sphinx-build`` as described in the project's
CLAUDE.md whenever modules are added, removed, or renamed.

``exclude_patterns`` drops sphinx-apidoc's own aggregator pages
(``multitool namespace``, ``multitool.data namespace``, and so on) from
the build. Their navigation is replaced by the hand-written group pages
(``core.rst``, ``data.rst``, ``roblox.rst``, ``ui.rst``, ``widgets.rst``),
which give the sidebar readable labels instead of dotted module paths.
Re-running sphinx-apidoc regenerates the excluded files but never touches
the hand-written ones, so this stays correct across reruns.
"""

import os
import sys

sys.path.insert(0, os.path.abspath("../.."))

project = "Multitool"
copyright = "BakedAleska"
author = "BakedAleska"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
]

templates_path = ["_templates"]
exclude_patterns = [
    "_build",
    "Thumbs.db",
    ".DS_Store",
    "api/modules.rst",
    "api/multitool.rst",
    "api/multitool.data.rst",
    "api/multitool.roblox.rst",
    "api/multitool.ui.rst",
    "api/multitool.widgets.rst",
]

autodoc_default_options = {
    "members": True,
    "undoc-members": True,
    "show-inheritance": True,
}

# The project's docstrings use single backticks for inline code (Markdown
# style) rather than reST's double backticks. Without this, a single
# backtick falls back to reST's default "title reference" role and renders
# as italics instead of code.
default_role = "literal"

html_theme = "furo"
html_title = "Multitool"
