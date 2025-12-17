"""Sphinx configuration for Contacts API documentation."""

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.abspath(".."))

project = "Contacts API"
current_year = datetime.now().year
copyright = f"{current_year}, Contacts"
author = "Contacts Team"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
]


templates_path = ["_templates"]
exclude_patterns: list[str] = []

html_theme = "alabaster"

html_static_path = ["_static"]
