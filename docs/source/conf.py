import inspect
import os
import re
import sys
import time

import sphinx_autodoc_typehints
from sphinx_autodoc_typehints import (
    format_annotation, get_annotation_args, get_annotation_class_name, get_annotation_module,
)


parentdir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, parentdir)

from woob import __version__


os.system('./genapi.py')

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#sys.path.append(os.path.abspath('.'))

# -- General configuration -----------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be extensions
# coming with Sphinx (named 'sphinx.ext.*') or your custom ones.

sys.path.append(os.path.abspath("./_ext"))

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.doctest',
    'sphinx.ext.todo',
    'sphinx.ext.coverage',
    'sphinx.ext.viewcode',
    'sorted-toctree',
    #'sphinx.ext.autosectionlabel',
    'sphinx.ext.intersphinx',
    'sphinx_autodoc_typehints',
    "sphinxcontrib.jquery",
    #'sphinxcontrib.autoprogram',

]

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# The suffix of source filenames.
source_suffix = '.rst'

# The encoding of source files.
#source_encoding = 'utf-8'

# The master toctree document.
master_doc = 'index'

# General information about the project.
project = u'woob'
copyright = '2010-%s, Romain Bignon' % time.strftime('%Y')

# The version info for the project you're documenting, acts as replacement for
# |version| and |release|, also used in various other places throughout the
# built documents.
#
# The short X.Y version.
version = __version__
# The full version, including alpha/beta/rc tags.
release = __version__

# The language for content autogenerated by Sphinx. Refer to documentation
# for a list of supported languages.
#language = None

# There are two options for replacing |today|: either, you set today to some
# non-false value, then it is used:
#today = ''
# Else, today_fmt is used as the format for a strftime call.
#today_fmt = '%B %d, %Y'

# List of documents that shouldn't be included in the build.
#unused_docs = []

# List of directories, relative to source directory, that shouldn't be searched
# for source files.
exclude_trees = []

# The reST default role (used for this markup: `text`) to use for all documents.
#default_role = None

# If true, '()' will be appended to :func: etc. cross-reference text.
#add_function_parentheses = True

# If true, the current module name will be prepended to all description
# unit titles (such as .. function::).
add_module_names = False

# If true, sectionauthor and moduleauthor directives will be shown in the
# output. They are ignored by default.
#show_authors = False

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = 'friendly'

# A list of ignored prefixes for module index sorting.
#modindex_common_prefix = []

# Have a class doc along with its __init__
#autoclass_content = 'monokai'
autodoc_member_order = 'bysource'
autodoc_preserve_defaults = True

intersphinx_mapping = {
    'py': ('https://docs.python.org/3', None),
    'requests': ('https://requests.readthedocs.io/en/latest/', None)
}

typehints_defaults = 'braces-after'
simplify_optional_unions = False

# Better display of default values
def new_format_default(app, default, is_annotated=True):
    if default is inspect.Parameter.empty:
        return None
    formatted = repr(default).replace("\\", "\\\\")

    m = re.match("<class '(.*)'>", formatted)
    if m:
        formatted = f':class:`~{m.group(1)}`'
    else:
        m = re.match("<(.*) object.*>", formatted)
        if m:
            formatted = f':class:`~{m.group(1)}()`'
        else:
            m = re.match('<(.*)>', formatted)
            if m:
                formatted = f':class:`~{m.group(1)}`'
            else:
                formatted = f':class:`{formatted}`'

    if is_annotated:
        if app.config.typehints_defaults.startswith("braces"):
            return f" (default: {formatted})"
        else:  # other option is comma
            return f", default: {formatted}"
    else:
        if app.config.typehints_defaults == "braces-after":
            return f" (default: {formatted})"
        else:
            return f"default: {formatted}"

sphinx_autodoc_typehints.format_default = new_format_default

# Do not display neither Optional nor Union, but only pipes.
def formatter(annotation, config):
    try:
        module = get_annotation_module(annotation)
        class_name = get_annotation_class_name(annotation, module)
        args = get_annotation_args(annotation, module, class_name)
    except ValueError:
        return str(annotation).strip("'")


    full_name = f"{module}.{class_name}" if module != "builtins" else class_name
    if full_name in ("types.UnionType", "typing.Union", "typing.Optional"):
        return " | ".join([format_annotation(arg, config) for arg in args])

    return None

typehints_formatter = formatter

# -- Options for HTML output ---------------------------------------------------

# The theme to use for HTML and HTML Help pages.  Major themes that come with
# Sphinx are currently 'default' and 'sphinxdoc'.
html_theme = 'alabaster'

# Theme options are theme-specific and customize the look and feel of a theme
# further.  For a list of options available for each theme, see the
# documentation.
html_theme_options = {
    'logo': 'logo.png',
    'logo_name': False,
    'logo_text_align': 'center',
    'show_powered_by': False,
}

# Add any paths that contain custom themes here, relative to this directory.
#html_theme_path = []

# The name for this set of Sphinx documents.  If None, it defaults to
# "<project> v<release> documentation".
#html_title = 'Woob development'

# A shorter title for the navigation bar.  Default is the same as html_title.
#html_short_title = None

# The name of an image file (relative to this directory) to place at the top
# of the sidebar.
#html_logo = '_static/logo.png'

# The name of an image file (within the static path) to use as favicon of the
# docs.  This file should be a Windows icon file (.ico) being 16x16 or 32x32
# pixels large.
html_favicon = '_static/favicon.png'

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']

#html_js_files = ['custom.js']

# If not '', a 'Last updated on:' timestamp is inserted at every page bottom,
# using the given strftime format.
#html_last_updated_fmt = '%b %d, %Y'

# If true, SmartyPants will be used to convert quotes and dashes to
# typographically correct entities.
html_use_smartypants = True

# Custom sidebar templates, maps document names to template names.
#html_sidebars = {
#    'index': ['indexsidebar.html'],
#}

# Additional templates that should be rendered to pages, maps page names to
# template names.
#html_additional_pages = {
#    'index': 'indexcontent.html'
#}

# If false, no module index is generated.
#html_use_modindex = True

# If false, no index is generated.
#html_use_index = True

# If true, the index is split into individual pages for each letter.
html_split_index = False

# If true, links to the reST sources are added to the pages.
html_show_sourcelink = False

# If true, an OpenSearch description file will be output, and all pages will
# contain a <link> tag referring to it.  The value of this option must be the
# base URL from which the finished HTML is served.
#html_use_opensearch = ''

# If nonempty, this is the file name suffix for HTML files (e.g. ".xhtml").
#html_file_suffix = ''

# Output file base name for HTML help builder.
htmlhelp_basename = 'woob' + release.replace('.', '')

# -- Options for LaTeX output --------------------------------------------------

# The paper size ('letter' or 'a4').
#latex_paper_size = 'letter'

# The font size ('10pt', '11pt' or '12pt').
#latex_font_size = '10pt'

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title, author, documentclass [howto/manual]).
latex_documents = [
    ('index', 'woob.tex', u'Woob Documentation',
     u'Woob Team', 'manual'),
]

# The name of an image file (relative to this directory) to place at the top of
# the title page.
#latex_logo = None

# For "manual" documents, if this is true, then toplevel headings are parts,
# not chapters.
#latex_use_parts = False

# Additional stuff for the LaTeX preamble.
#latex_preamble = ''

# Documents to append as an appendix to all manuals.
#latex_appendices = []

# If false, no module index is generated.
#latex_use_modindex = True
