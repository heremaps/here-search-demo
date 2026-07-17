# Minimal Sphinx configuration for Markdown support and Furo theme
import os
import sys

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
