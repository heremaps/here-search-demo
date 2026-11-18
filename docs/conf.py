###############################################################################
#
# Copyright (c) 2023 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

# Minimal Sphinx configuration for Markdown support and Furo theme
import os
import sys
import warnings

# sphinx-autodoc-typehints is pinned to ==3.6.1 (highest available in the ELM
# index); that version calls a Sphinx API deprecated for removal in Sphinx 10,
# emitting a RemovedInSphinx10Warning once per documented object. It is harmless
# on the current Sphinx 9.x line, so silence the noise until a newer
# sphinx-autodoc-typehints becomes available.
warnings.filterwarnings(
    "ignore",
    message=r".*_RstSnippetParser\.set_application.*is deprecated.*",
)

sys.path.insert(0, os.path.abspath("../src"))
from here_search_demo import __version__

project = 'here-search-demo'
author = 'HERE Technologies'
release = __version__
version = __version__

extensions = [
    'myst_parser',
    'sphinx.ext.autodoc',
    'sphinx.ext.mathjax',
    'sphinx_autodoc_typehints',
]

html_theme = 'furo'

source_suffix = {
    '.rst': 'restructuredtext',
    '.md': 'markdown',
}

exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

html_static_path = ['_static']
html_css_files = ['custom.css']
html_js_files = ['layout.js']

# Allow fenced blocks like ```math to be treated as MyST {math} directives.
myst_fence_as_directive = ["math"]

# Enable inline $...$ and $$...$$ math rendering.
myst_enable_extensions = ["dollarmath"]
