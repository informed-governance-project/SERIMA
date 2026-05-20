# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------


import os
import sys

import django

sys.path.insert(0, os.path.abspath(".."))
os.environ["DJANGO_SETTINGS_MODULE"] = "governanceplatform.settings"
os.environ["READTHEDOCS"] = "True"
django.setup()

project = "NIS Incident Notification Platform"
copyright = "2023-2026 Luxembourg House of Cybersecurity"
author = "NC3 Team <info@nc3.lu>"

# The full version, including alpha/beta/rc tags
release = "0.5.14"


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "sphinx.ext.autodoc",
    "sphinxcontrib.openapi",
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

numfig = True


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = "sphinx_book_theme"

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]

html_title = "NISINP"
html_theme_options = {
    "path_to_docs": "docs",
    "repository_url": "https://github.com/informed-governance-project/NISINP",
    "launch_buttons": {
        "binderhub_url": "https://github.com/informed-governance-project/NISINP",
    },
    "use_edit_page_button": True,
    "use_issues_button": True,
    "use_repository_button": True,
    "use_download_button": True,
    "home_page_in_toc": True,
}


# -- Options for LaTeX output --------------------------------------------------

latex_engine = "pdflatex"

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title, author, documentclass [howto/manual]).
latex_documents = [
    ("index", "nisinp.tex", "NIS Incident Notification Platform", "NC3-LU", "howto"),
]

latex_show_urls = True
latex_show_pagerefs = True

ADDITIONAL_PREAMBLE = r"""
\setcounter{tocdepth}{3}
"""
