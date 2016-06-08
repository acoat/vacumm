# -*- coding: utf-8 -*-
#
# VACUMM documentation build configuration file, created by
# sphinx-quickstart on Mon Apr 26 13:54:38 2010.
#
# This file is execfile()d with the current directory set to its containing dir.
#
# Note that not all possible configuration values are present in this
# autogenerated file.
#
# All configuration values have a default; values that are commented out
# serve to show the default.

import sys, os, subprocess
from matplotlib import use ; use('Agg')

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#sys.path.append(os.path.abspath('.'))
for path in ('../../../lib/python', '../../../lib/python/vacumm',
        'sphinxext', '../../..'):
    cfile = sys._getframe(0).f_code.co_filename
    cdir = os.path.dirname(cfile)
    path = os.path.abspath(os.path.join(cdir, path))
    sys.path.insert(0, path)

# -- General configuration -----------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be extensions
# coming with Sphinx (named 'sphinx.ext.*') or your custom ones.
extensions = [
        'sphinx.ext.inheritance_diagram',
        'sphinx.ext.autodoc',
        'sphinx.ext.autosummary',
        'sphinx.ext.intersphinx',
        'sphinx.ext.todo',
        'sphinx.ext.pngmath',
        'sphinx.ext.ifconfig',
        'sphinx.ext.extlinks',
        'sphinx.ext.viewcode',
        'sphinxcontrib.cheeseshop',
        'sphinxcontrib.ansi',
        'sphinxcontrib.programoutput',
        'sphinxfortran.fortran_domain',
        'sphinxfortran.fortran_autodoc',
        'vacumm.sphinxext.overview',
#        'vacumm.sphinxext.docversions',
        'gen_gallery',
        'gen_cmaps',
        'gen_binhelps',
        ]
import vacumm
vacumm.docfiller_verbose = True

# Add any paths that contain templates here, relative to this directory.
templates_path = ['templates']

# The suffix of source filenames.
source_suffix = '.rst'

# The encoding of source files.
#source_encoding = 'utf-8'

# The master toctree document.
master_doc = 'index'

# General information about the project.
project = u'VACUMM'
copyright = u'2010-2015, Actimar/IFREMER'

# The version info for the project you're documenting, acts as replacement for
# |version| and |release|, also used in various other places throughout the
# built documents.
import setup
version = setup.version_sphinx
release = setup.release_sphinx

# Import of this file or use through sphinx?
callfromsphinx = (os.path.exists('contents.rst') and
    os.path.abspath(__file__) == __file__)

# The language for content autogenerated by Sphinx. Refer to documentation
# for a list of supported languages.
language = 'en'

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
show_authors = True

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = 'sphinx'

# A list of ignored prefixes for module index sorting.
modindex_common_prefix = ['vacumm.']

trim_footnote_reference_space = True

numfig = True

# -- Options for HTML output ---------------------------------------------------

# The theme to use for HTML and HTML Help pages.  Major themes that come with
# Sphinx are currently 'default' and 'sphinxdoc'.
html_theme = 'sphinxdoc'

# Theme options are theme-specific and customize the look and feel of a theme
# further.  For a list of options available for each theme, see the
# documentation.
#html_theme_options = {}
#html_theme_options = {
    #"collapsiblesidebar": "true"
#}

# Add any paths that contain custom themes here, relative to this directory.
html_theme_path = ['themes']

html_style = 'vacumm.css'

# The name for this set of Sphinx documents.  If None, it defaults to
# "<project> v<release> documentation".
html_title = 'VACUMM v%(release)s documentation'%locals()

# A shorter title for the navigation bar.  Default is the same as html_title.
html_short_title = 'VACUMM'

# The name of an image file (relative to this directory) to place at the top
# of the sidebar.
html_logo = 'static/logo_vacumm.png'

# The name of an image file (within the static path) to use as favicon of the
# docs.  This file should be a Windows icon file (.ico) being 16x16 or 32x32
# pixels large.
#html_favicon = None

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['static']

# If not '', a 'Last updated on:' timestamp is inserted at every page bottom,
# using the given strftime format.
html_last_updated_fmt = '%d %b %Y'

# If true, SmartyPants will be used to convert quotes and dashes to
# typographically correct entities.
#html_use_smartypants = True

# Custom sidebar templates, maps document names to template names.
#html_sidebars = {}

# Additional templates that should be rendered to pages, maps page names to
# template names.
html_additional_pages = {'index':'index.html', 'gallery':'gallery.html'}

# If false, no module index is generated.
#html_use_modindex = True

# If false, no index is generated.
#html_use_index = True

# If true, the index is split into individual pages for each letter.
#html_split_index = False

# If true, links to the reST sources are added to the pages.
#html_show_sourcelink = True

# If true, an OpenSearch description file will be output, and all pages will
# contain a <link> tag referring to it.  The value of this option must be the
# base URL from which the finished HTML is served.
#html_use_opensearch = ''

# If nonempty, this is the file name suffix for HTML files (e.g. ".xhtml").
#html_file_suffix = ''

# Output file base name for HTML help builder.
htmlhelp_basename = 'VACUMMdoc'


# -- Options for LaTeX output --------------------------------------------------

# The paper size ('letter' or 'a4').
latex_paper_size = 'a4'

# The font size ('10pt', '11pt' or '12pt').
#latex_font_size = '10pt'

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title, author, documentclass [howto/manual]).
latex_documents = [
  ('index', 'VACUMM.tex', u'Documentation de VACUMM',
   u'Actimar / IFREMER', 'manual'),
]

# The name of an image file (relative to this directory) to place at the top of
# the title page.
latex_logo = 'static/logo_vacumm.pdf'

# For "manual" documents, if this is true, then toplevel headings are parts,
# not chapters.
#latex_use_parts = False

# Additional stuff for the LaTeX preamble.
latex_preamble = r"""
   \usepackage{vacumm}
"""
latex_additional_files = ['static/vacumm.sty']


# Documents to append as an appendix to all manuals.
#latex_appendices = []

# If false, no module index is generated.
#latex_use_modindex = True


# Intersphinx
intersphinx_mapping = {
    'python':('http://docs.python.org/', None),
    'matplotlib':('http://matplotlib.org',None),
    'basemap':('http://matplotlib.org/basemap',None),
    'numpy':('http://docs.scipy.org/doc/numpy', None),
    'scipy':('http://docs.scipy.org/doc/scipy/reference', None),
    'sphinx':('http://sphinx.pocoo.org', None),
    'http://docs.python.org/dev': None,
    }

# Extlinks
extlinks = {
    'basemap': ('http://matplotlib.github.com/basemap/%s', None),
    'sphinx': ('http://sphinx.pocoo.org/%s', None),
    'rstdoc': ('http://docutils.sourceforge.net/docs/ref/rst/%s', None),
    }


# Python overview
overview_title_overview = False
overview_title_content = False
overview_columns = 3

# VACUMM config
if callfromsphinx:
    from vacumm.config import write_default_config
    write_default_config('vacumm.cfg')

unused_docs = ['tutorials/bathy.shorelines.sealevel.rst']

todo_include_todos = True

# Inheritance diagram
inheritance_graph_attrs = dict(rankdir="TB", size='"6.0, 8.0"', ratio='compress')
inheritance_node_attrs = dict(shape='ellipse', fontsize=10, height=.6,
                              color='orange', style='filled')
inheritance_edge_attrs = dict(penwidth=1)


## Help of scripts
## TODO: Create an extension for generating these rst help files
#if callfromsphinx:
#    scripts = ['*.py']
#    binrstdir = os.path.abspath('bin')
#    if not os.path.isdir(binrstdir):
#        os.makedirs(binrstdir)
#    import glob
#    from vacumm.misc.config import opt2rst
#    for ss in scripts:
#        for script in glob.glob(os.path.abspath(os.path.join('../../../bin', ss))):
#
#            # Output rst file
#            rstfile = os.path.join(binrstdir,
#                '%s.help.txt'%os.path.basename(script[:-3]))
#
#            # Checks before processing
#            if (os.path.exists(rstfile) and
#                os.stat(script).st_mtime < os.stat(rstfile).st_mtime):
#                continue
#
#            # Generate help
#            try:
#                std,err = subprocess.Popen([script, "-h"], stdout=subprocess.PIPE,
#                    stderr=subprocess.PIPE).communicate()
#            except:
#                continue
#            std = std.decode('utf-8', 'replace')
#            err = err.decode('utf-8', 'replace')
#            if not err is not None: continue
#            f = open(rstfile, 'w')
#            f.write(opt2rst(std))
#            f.close()
#            print 'Saved', rstfile


# Gallery
gen_gallery_paths = {
    'tutorials':{'figdir':'../../../scripts/tutorials', 'rstdir':'tutorials',
        'title':'Tutorials'},
    'test':{'figdir':'../../../scripts/test', 'rstdir':'tests',
        'title':'Test scripts'},
    'courses':{'figdir':'../../../scripts/courses', 'rstdir':'courses',
        'title':'Courses'},
}
#gen_gallery_root = 'gallery'
#gen_gallery_skips = [] # basenames to skip
#gen_gallery_nmax = 3 # max number of muti-figures

# Colormaps
gen_cmaps_prefix = 'misc-color-'
gen_cmaps_extra_list = [
    # (function name, kwargs, figfile short name (no prefix+no ext)),
    ('cmap_jets', dict(stretch=0.6), 'vacumm_jets+60'),
    ('cmap_jets', dict(stretch=-0.6), 'vacumm_jets-60'),
    ('cmap_magic', dict(), 'vacumm_magic'),
    ('cmap_magic', dict(n=10), 'vacumm_magic-n10'),
    ('cmap_magic', dict(anomaly=True), 'vacumm_magic-anom'),
    ('cmap_magic', dict(positive=True), 'vacumm_magic-pos'),
    ('cmap_magic', dict(negative=True), 'vacumm_magic-neg'),
    ('cmap_rainbow', dict(n=5, stretcher='reduced_green'), 'vacumm_rainbow'),
]

# Autodoc (python)
autodoc_default_flags = ['members', 'show-inheritance', 'undoc-members']

# Configuration for programoutput extension
#doesn't works...#programoutput_prompt_template = '[user@host ~]$ %(command)s\n\n%(output)s' # default is: '$ %%(command)s\n%%(output)s'
programoutput_use_ansi = True # default is: False

# Fortran autodoc
fortran_src = [os.path.abspath('../../../lib/python/vacumm/misc/grid/interp.f90')]

# Docversions
docversions_subpath_doc = 'doc/sphinx'
docversions_index_html = 'contents.html'


def setup(app):
    app.add_object_type('confopt', 'confopt',
        objname='configuration option',
        indextemplate='pair: %s; configuration option')
    app.add_object_type('confsec', 'confsec',
        objname='configuration section',
        indextemplate='pair: %s; configuration section')

