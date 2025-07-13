# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

import io

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import os
import sys
from contextlib import redirect_stderr, redirect_stdout
from datetime import date
from pathlib import Path

# from recommonmark.parser import CommonMarkParser

sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("../../src"))

from freva_deployment import __version__
from freva_deployment.cli import main_cli
from freva_deployment.utils import config_dir

toml_config_file = (
    Path(__file__).parent.parent
    / "assets"
    / "share"
    / "freva"
    / "deployment"
    / "config"
    / "inventory.toml"
)
toml_config = toml_config_file.read_text()


def get_cli_output(*args, format="md"):
    if args:
        cmd = list(args) + ["--help"]
    else:
        cmd = ["--help"]
    command = f"deploy-freva {' '.join(args)} --help"
    buf = io.StringIO()
    try:
        with redirect_stderr(buf), redirect_stdout(buf):
            main_cli(cmd)
    except SystemExit:
        pass
    output = buf.getvalue()
    if format == "md":
        return f"```console\n{command}\n{output}```"
    else:
        return f"{command}\n{output}\n"


cli_tui = get_cli_output()
cli_cmd = get_cli_output("cmd")
cli_mig = get_cli_output("migrate")
cli_config = get_cli_output("config")
# -- Project information -----------------------------------------------------

project = "freva-deployment"
copyright = f"{date.today().year}, DKRZ - CLINT"
author = "Climate Informatics and Technology"

# The full version, including alpha/beta/rc tags
release = __version__


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.intersphinx",
    "sphinx.ext.napoleon",
    "sphinx_copybutton",
    "sphinx_togglebutton",
    "sphinxext.opengraph",
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = "pydata_sphinx_theme"
html_logo = "_static/freva_owl.svg"
html_favicon = "_static/freva_owl.svg"
# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_sidebars = {"pagename": []}
html_static_path = ["_static"]
html_context = {
    "github_user": "freva-org",
    "github_repo": "freva-admin",
    "github_version": "main",
    "doc_path": "docs",
}
html_sidebars = {
    "community/index": [
        "sidebar-nav-bs",
        "custom-template",
    ],  # This ensures we test for custom sidebars
}

html_theme_options = {
    "icon_links": [
        {
            "name": "GitHub",
            "url": "https://github.com/freva-org/freva-admin",
            "icon": "fa-brands fa-github",
        },
        {
            "name": "PyPI",
            "url": "https://pypi.org/project/freva-deployment",
            "icon": "fa-custom fa-pypi",
        },
    ],
    "navbar_center": ["navbar-nav"],  # Add navigation links to the left sidebar
    "collapse_navigation": False,
    "navigation_depth": 4,
    "navbar_align": "left",
    "show_nav_level": 2,
    "secondary_sidebar_items": ["page-toc"],
}
html_sidebars = {"**": ["sidebar-nav-bs", "sidebar-ethical-ads"]}
html_meta = {
    "description": "Admin guide for freva.",
    "keywords": "freva, climate, data analysis, evaluation, framework, climate science",
    "author": "Freva Team",
    "og:title": "Freva – Free Evaluation System Framework",
    "og:description": "Admin guide for Freva.",
    "og:type": "website",
    "og:url": "https://freva-org.github.io/freva-admin/",
    "og:image": "https://freva-org.github.io/freva-admin/_images/freva_flowchart-new.png",
    "twitter:card": "summary_large_image",
    "twitter:title": "Freva – Evaluation System Framework",
    "twitter:description": "Search, analyse and evaluate climate model data.",
    "twitter:image": "https://freva-org.github.io/freva-admin/_images/freva_flowchart-new.png",
}

ogp_site_url = "https://freva-org.github.io/freva-admin"
opg_image = (
    "https://freva-org.github.io/freva-admin/_images/freva_flowchart-new.png",
)
ogp_type = "website"
ogp_custom_meta_tags = [
    '<meta name="twitter:card" content="summary_large_image">',
    '<meta name="keywords" content="freva, climate, data, evaluation, science, reproducibility">',
]
# -- MyST options ------------------------------------------------------------

# This allows us to use ::: to denote directives, useful for admonitions
myst_enable_extensions = ["colon_fence", "linkify", "substitution"]
myst_heading_anchors = 2
myst_substitutions = {
    "rtd": "[Read the Docs](https://readthedocs.org/)",
    "version": __version__,
    "cli_tui": cli_tui,
    "cli_cmd": cli_cmd,
    "cli_mig": cli_mig,
    "cli_compose": get_cli_output("compose"),
    "cli_config": cli_config,
    "cli_config_get": get_cli_output("config", "get"),
    "cli_config_set": get_cli_output("config", "get"),
    "toml_config": f"```toml\n{toml_config}\n```",
}
myst_url_schemes = {
    "http": None,
    "https": None,
    "release": f"https://github.com/freva-org/freva-admin/releases/tag/v{release}",
    "exe": f"https://github.com/freva-org/freva-admin/releases/download/v{release}/deploy-freva-v{release}-{{{{path}}}}",
}
# Substitutions
rst_prolog = """
.. version replace:: {version}
""".format(
    version=__version__,
)

cli_output_dir = Path(__file__).parent / "_generated"
cli_output_dir.mkdir(exist_ok=True, parents=True)

(cli_output_dir / "compose.txt").write_text(
    get_cli_output("compose", format="rst")
)


# ReadTheDocs has its own way of generating sitemaps, etc.
if not os.environ.get("READTHEDOCS"):
    extensions += ["sphinx_sitemap"]

    html_baseurl = os.environ.get("SITEMAP_URL_BASE", "http://127.0.0.1:8000/")
    sitemap_locales = [None]
    sitemap_url_scheme = "{link}"

# specifying the natural language populates some key tags
language = "en"
