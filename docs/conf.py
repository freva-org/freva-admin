"""Sphinx configuration for the Freva administrator guide."""

from datetime import date

project = "Freva administration"
copyright = f"{date.today().year}, DKRZ and the Freva contributors"
author = "Freva Team"
release = "2.0"

extensions = [
    "myst_parser",
    "sphinx_copybutton",
    "sphinxext.opengraph",
]

exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]
templates_path = ["_templates"]
html_theme = "pydata_sphinx_theme"
html_logo = "_static/freva_owl.svg"
html_favicon = "_static/freva_owl.svg"
html_static_path = ["_static"]
html_context = {
    "github_user": "freva-org",
    "github_repo": "freva-admin",
    "github_version": "main",
    "doc_path": "docs",
}
html_theme_options = {
    "icon_links": [
        {
            "name": "GitHub",
            "url": "https://github.com/freva-org/freva-admin",
            "icon": "fa-brands fa-github",
        }
    ],
    "show_nav_level": 2,
    "navigation_depth": 4,
}
html_meta = {
    "description": "Administration and deployment guide for Freva.",
    "keywords": "freva, ansible, podman, quadlet, helm, kubernetes",
}

myst_enable_extensions = ["colon_fence"]
myst_heading_anchors = 3
ogp_site_url = "https://freva-org.github.io/freva-admin"
ogp_type = "website"

language = "en"
