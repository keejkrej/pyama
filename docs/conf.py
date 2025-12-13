"""Sphinx configuration for PyAMA documentation."""

import os
import sys

# -- Project information -----------------------------------------------------
project = 'PyAMA'
copyright = '2024, PyAMA Development Team'
author = 'PyAMA Development Team'
release = ''
version = ''

# -- General configuration ---------------------------------------------------
extensions = [
    'myst_parser',
    'sphinx_copybutton',
]

templates_path = ['_templates']
exclude_patterns = []

# MyST options
myst_enable_extensions = [
    'colon_fence',
    'deflist',
    'html_admonition',
    'substitution',
    'tasklist',
]

# -- Options for HTML output -------------------------------------------------
html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']

html_theme_options = {
    'collapse_navigation': False,
    'display_version': False,
    'logo_only': True,
}

# -- Sidebars ---------------------------------------------------------------
html_sidebars = {
    '**': [
        'relations.html',
        'searchbox.html',
    ],
}

# -- Copy button configuration -----------------------------------------------
copybutton_prompt_text = r">>> |\.\.\. |\$ |In \[\d*\]: | {2,5}\.\.\.: | {5,8}: "
copybutton_prompt_is_regexp = True

# -- Nitpicky mode for refs -------------------------------------------------
nitpicky = True
nitpick_ignore = [
    ('py:class', 'None'),
]
