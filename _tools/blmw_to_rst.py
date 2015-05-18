
# LICENSE:
# Permission is granted to use, copy, modify, and/or distribute this
# software for any purpose.

# INFO:
# - this script assumes UNIX line endings ('\n')

# TODO:
# - text wrap
# - inline images, might be hard to tell apart from figures in MediaWiki
#   most of the time, figures are desired
# - various things marked as TODO
# - internal links

import os
import re
import mwparserfromhell
from mwparserfromhell import nodes
from textwrap import indent


#================ CONFIG ====================
# transfer alignment option from MediaWiki images to RST
# may or may not work well with certain themes
ENABLE_IMAGE_ALIGNMENT = False

WIKI_HOST = 'http://wiki.scribus.net'
TITLE_PREFIX = "Doc:2.6/Manual/"

INDENTATION = ' ' * 3

TITLE_CHARS = ('#', '*', '=', '-', '^', '"', '~')

# slows things down, unimportant checks - but nice for final output
USE_PEDANTIC = True

# 118 is real limit, but use lower since this is performed as a pre-process
WIDTH = 95
#============================================

EMPTY_STRING = ""
RIGHT_ARROW = '\u2192'


def MARKUP(l, r):
    return ('┤' + l, r + '├')

M_BOLD = MARKUP('**', '**')
M_LITERAL = MARKUP('``', '``')
M_ITALIC = MARKUP('*', '*')
M_SUP = MARKUP(':sup:`', '`')
M_SUB = MARKUP(':sub:`', '`')
M_STRONG = MARKUP(':strong:`', '`')
M_MATH = MARKUP(':math:`', '`')
M_GUILABEL = MARKUP(':guilabel:`', '`')
M_DOC = MARKUP(':doc:`', '`')
M_ABBR = MARKUP(':abbr:`', '`')
M_KBD = MARKUP(':kbd:`', '`')
M_MENU = MARKUP(':menuselection:`', '`')
M_EXTLINK = MARKUP('`', '`__')

ALL_MARKUP = (
    M_BOLD,
    M_LITERAL,
    M_ITALIC,
    M_SUP,
    M_SUB,
    M_STRONG,
    M_MATH,
    M_GUILABEL,
    M_DOC,
    M_ABBR,
    M_KBD,
    M_MENU,
    M_EXTLINK
)

TAG_TO_MARKUP = {
    'b': M_BOLD,
    'code': M_LITERAL,
    'nowiki': M_LITERAL,
    'tt': M_LITERAL,
    'i': M_ITALIC,
    'sup': M_SUP,
    'sub': M_SUB,
    'strong': M_STRONG,
    'math': M_MATH,
}


def wikiurl(link):
    return "%s/index.php/%s" % (WIKI_HOST, link)

# TODO


def wikipath_to_rstpath(path):
    return path[len('2.6/Manual/'):].lower().replace(' ', '_').replace("'", "")


def is_image_file(filename):
    filename = filename.lower().strip()
    if filename.endswith(('.jpg', '.jpeg', '.png', '.gif')):
        return True
    return False


def wrap_smart(l, width):
    """
    Visually pleasing wrap, taking punctuation into account.
    """
    import re

    # first explode
    if not hasattr(wrap_smart, "cache"):
        wrap_smart.cache = cache = []
        s = [r"([^X]+X+\s+)".replace("X", c) for c in (r"\,", r"\.", ";", ":", r"\)", "\]")]
        for e in s:
            r = re.compile(e)
            wrap_smart.cache.append(r)

        r = re.compile(r"(\[\[[^\[]*)")
        wrap_smart.cache.append(r)

        r = re.compile(r"(\([^\(]*)")
        wrap_smart.cache.append(r)
        del r
        wrap_smart.cache_ws = cache_ws = re.compile(r"(\s)")
    else:
        cache = wrap_smart.cache
        cache_ws = wrap_smart.cache_ws


    # --------------------
    # iteratively re-split
    l = [l]

    # -------------------
    # split on delimiters
    for r in cache:
        i = len(l)
        while i > 0:
            i -= 1
            l[i : i + 1] = [w for w in re.split(r, l[i]) if w]

    # -------------------------------------
    # explode all too-long lines into words
    i = len(l)
    while i > 0:
        i -= 1
        if len(l[i]) > width:
            l[i : i + 1] = re.split(cache_ws, l[i])

    # ------------------------
    # now merge based on width
    i = 0
    while i < len(l) - 1:
        if len(l[i].lstrip()) + len(l[i + 1].rstrip()) < width:
            l[i : i + 2] = [l[i] + l[i + 1]]
        else:
            l[i] = l[i].strip()
            i += 1

    return l


from collections import defaultdict
# a record type used to collect information during MediaWiki AST traversal


class ConversionReport:
    __slots__ = (
        "arguments",
        "comments",
        "external_links",
        "headings",
        "texts",

        "html_entities",
        "html_tags",
        "templates",
        "wikilinks",

        "fixme",
        "deleted",
        "images",
        )

    def __init__(self):
        self.arguments = []
        self.comments = []
        self.external_links = []
        self.headings = []
        self.texts = []

        self.html_entities = defaultdict(list)
        self.html_tags = defaultdict(list)
        self.templates = defaultdict(list)
        self.wikilinks = defaultdict(list)

        self.fixme = defaultdict(list)
        self.deleted = defaultdict(list)
        self.images = []


# preprocessing step for MediaWiki code
def preprocess(mw):
    # escape the backtick
    mw = mw.replace('`', '\`')

    # fancier arrows
    mw = mw.replace('-&gt;', RIGHT_ARROW)

    mw = mw.replace("\u201C", '"')
    mw = mw.replace("\u201D", '"')

    mw = mw.replace("\u2018", "'")
    mw = mw.replace("\u2019", "'")
    mw = mw.replace("\u8211", "-")
    mw = mw.replace("\u2013", "-")

    # get rid of __TOC__
    mw = mw.replace('__TOC__', EMPTY_STRING)

    # remove left-to-right mark: '‎' (it's between the quotes, but it's an invisible char!)
    # this occurs at the end of several image/file links for some reason
    mw = mw.replace('\u200e', EMPTY_STRING)

    # Table syntax like this is not supported by mwparserfromhell
    #
    #   {|align=left|... content ... |}
    #
    #  replace with a pseudo-template like
    #
    #   {{Table|align=left|...content ...|}}
    #
    mw = re.sub(r'(?<!\{)\{\|', '{{Table|', re.sub(r'\|\}(?!\})', '}}', mw))
    # using ! instead of | in tables (for bolded markup) is not supported
    # changed to a mock row argument instead
    # TODO actually support parsing this
    #mw = mw.replace('\n! ', '\n| special="bold"')

    def replace_header(line):
        line = line.strip()
        if line.startswith('!'):
            return '| special="bold"|' + line[1:].replace("!!", '||')
        else:
            return line
    mw = '\n'.join([replace_header(line) for line in mw.split('\n')])

    # table header syntax (rows starting with '+')
    # TODO actually support parsing this
    mw = mw.replace('\n|+', '\n| special="head"|')

    # indent definition lists of the format:
    #
    # ;term
    # :definition
    # :;subterm
    # ::subdefinition
    #
    # also insert newline for the format:
    #
    # ;term : definition
    #
    def replace_def(m):
        indents = len(m.group(1))
        res = []
        if m.group(1):
            res.append(indents * ':')
        head, _, tail = m.group(2).partition(': ')
        res.append(head.strip())
        if tail != EMPTY_STRING:
            res.append('\n' + ((indents + 1) * ':') + tail.strip())
        return ''.join(res)
    mw = '\n'.join(re.sub(r'^(:*)?;(.*)', replace_def, s)
                   for s in mw.split('\n'))

    # wrap long lines (body text only for now)
    if USE_PEDANTIC:
        mw = mw.split("\n")
        i = len(mw) - 1
        while i >= 0:
            # simple cleanup
            mw[i] = mw[i].rstrip()

            # 118 is real limit, but RST may expand a bit
            if len(mw[i]) > WIDTH and mw[i][0].isalnum():
                ok = True
                if "[[" in mw[i]:
                    ok = False
                if ok:
                    mw[i:i + 1] = wrap_smart(mw[i], WIDTH)
            i -= 1
        mw = '\n'.join(mw)


    return mw


# postprocessing step after AST-to-RST conversion
#
# Handles all the inserted control tokens (°,┴,┤,├), which
# account for peculiarities in the RST syntax
def postprocess(rst):
    # remove all markup that ends up with no content, see remarkup()
    for l, r in ALL_MARKUP:
        rst = rst.replace(l + r, EMPTY_STRING)

    # markup like this fails in RST, no spaces are allowed:
    # *  markup *
    # therefore, swap the whitespace around with the markup
    #   *markup*
    def replace_swap(m):
        return '%s%s' % (m.group(2), m.group(1))
    for l, r in ALL_MARKUP:
        rst = re.sub(r'(\s+)(%s)' % re.escape(r), replace_swap, rst)
        rst = re.sub(r'(%s)(\s+)' % re.escape(l), replace_swap, rst)

    #---------------------------------------------------------
    # ° - bullet points
    #---------------------------------------------------------
    # ensure that there is a blank line in front of every bullet point list
    rst_lines = rst.split('\n')
    i = 1
    i_prev_bullet = False
    while i < len(rst_lines):
        if '°' in rst_lines[i]:
            if '°' not in rst_lines[i - 1]:
                rst_lines[i] = '\n' + rst_lines[i]
            i_prev_bullet = True
        else:
            # ensure newline after bullets
            if i_prev_bullet:
                if rst_lines[i] and not rst_lines[i].isspace():
                    rst_lines.insert(i, "")
            i_prev_bullet = False
        i += 1
    rst = '\n'.join(rst_lines)
    del i_prev_bullet
    # replace bullet point token with appropriate indentation and single bullet

    def replace_bp(m):
        return "%s- " % ((len(m.group(0)) // len('°') - 1) * '  ')
    rst = re.sub('(°)+', replace_bp, rst)

    # XXX, removing double spaces after isnt so trivial!
    # infact this is needed for RST pedantic indentation rules
    rst = rst.replace("-  ", "- ")

    #--------------------------------------------------------
    # ┴ - at least one preceeding blank line is required
    #--------------------------------------------------------
    rst_lines = list(rst.split('\n'))
    i = 1
    while i < len(rst_lines):
        if '┴' in rst_lines[i]:
            if rst_lines[i - 1] != EMPTY_STRING:
                rst_lines[i] = '\n' + rst_lines[i].replace('┴', EMPTY_STRING)
            else:
                rst_lines[i] = rst_lines[i].replace('┴', EMPTY_STRING)
        i += 1
    rst = '\n'.join(rst_lines)

    #--------------------------------------------------------
    # ├ - insert escaped space if next character is ???
    #--------------------------------------------------------
    def replace_sr(m):
        next_char = m.group(1)
        if next_char is not None:
            # if re.match(r'[a-zA-Z`\*→]', next_char):
            if re.match(r'\S', next_char):
                return r'\ ' + next_char
            else:
                return next_char
        else:
            return EMPTY_STRING
    rst = re.sub('├(.)?', replace_sr, rst)

    #--------------------------------------------------------
    # ┤ - insert escaped space if previous char is ???
    #--------------------------------------------------------
    def replace_sl(m):
        prev_char = m.group(1)
        if prev_char is not None:
            # if re.match(r'[a-zA-Z`\*]', prev_char):
            if re.match(r'\S', prev_char):
                return prev_char + r'\ '
            else:
                return prev_char
        else:
            return EMPTY_STRING
    rst = re.sub('(.)?┤', replace_sl, rst)

    # prevent hoz rule being confused with title
    rst = rst.replace("\n----\n", "\n\n----\n\n")


    # \t are used for convenience, but should not be in final output
    rst = rst.replace('\t', INDENTATION)

    # TODO ensure newlines before definition lists

    if USE_PEDANTIC:
        # double-newlines only
        len_curr = len(rst)
        len_prev = -1
        while len_curr != len_prev:
            rst = rst.replace("\n\n\n\n", "\n\n\n")
            len_prev = len_curr
            len_curr = len(rst)

    return rst


# creates a string with a 'painted' RST table
# takes a list of rows, each item being a list of column items
def rst_paint_table(table):
    col_count = max(len(row) for row in table)
    # split up items into a list of lines
    # find the minimum width of each column
    col_widths = [1] * col_count
    for x, row in enumerate(table):
        for y, content in enumerate(row):
            # postprocess now so that layout does not get messed up later
            content_split = postprocess(content).split('\n')
            for line in content_split:
                col_widths[y] = max(col_widths[y], len(line))
            row[y] = content_split

    # find the minimum height (number of lines) of each row
    # pad with empty lines for equal heights
    row_heights = [1] * len(table)
    for x, row in enumerate(table):
        for content_split in row:
            row_heights[x] = max(row_heights[x], len(content_split))
        for y, content_split in enumerate(row):
            content_split += [EMPTY_STRING] * \
                (row_heights[x] - len(content_split))

    total_width = sum(col_widths) + col_count - 1
    border_line = '+%s+' % ('+'.join('-' * width for width in col_widths))

    # pad content to proper width, write final lines
    lines = []
    lines.append(border_line)
    for x, row in enumerate(table):
        for h in range(row_heights[x]):
            line = []
            for y, content_split in enumerate(row):
                line.append(content_split[h].ljust(col_widths[y]))
            lines.append('+%s+' % ('|'.join(line).ljust(total_width)))
        lines.append(border_line)
    return '\n'.join(lines)


def rst_admonition(class_, title, body, options=None):
    header = "\n.. admonition:: %s\n\t:class: %s\n" % (title, class_)
    return "%s\n%s\n\n" % (header, indent('\n'.join(body), INDENTATION))


def rst_directive(directive, arg, body):
    if arg:
        header = "\n.. %s:: %s\n\t:class: %s\n" % (directive, arg)
    else:
        header = "\n.. %s::\n" % (directive)

    return "%s\n%s\n\n" % (header, indent('\n'.join(body), INDENTATION))


# RST fails even at the simplest of nested markup, which unfortunately is very common in the Blender Wiki
#
#  use this function to turn e.g. *No nesting :guilabel:`allowed` anymore!*
#                            into *No nesting *:guilabel:`allowed`* anymore!*
#
# hopefully this results in a half-decent approximation to the original intent
def remarkup(content, current_markup, previous):
    l, r = current_markup
    if previous is not None:
        pl, pr = previous
        return ''.join((pr, l, content, r, pl))
    else:
        return ''.join((l, content, r))


# convert a mwparserfromhell MediaWiki AST to a string
# returns a tuple with the (already postprocessed) RST string and the ConversionReport
# a ConversionReport may optionally be passed to gather information across
# multiple invocations
def convert_mw(start_node, report=None):
    if report is None:
        report = ConversionReport()

    # convenience functions to return from convert() with
    def FIXME(node, reason="Undefined"):
        report.fixme[reason].append(node)
        print("FIXME(%s)" % (reason))
        return "\nFIXME(%s;\n%s\n)" % (reason, node)

    def DELETE(node, reason="Undefined"):
        report.deleted[reason].append(node)
        return EMPTY_STRING

    def COMMENT(node, text):
        conv = ".. %s ." % (indent(text, INDENTATION))
        report.comments.append(node)
        return conv

    # convert() is the main recursive function to walk the MediaWiki AST
    # returns strings, always
    #
    # strip: if True, no further markup is allowed
    # markup: the current markup (or None), see usage of remarkup()
    def convert(node, strip, markup):
        # only ast nodes allowed!
        if node is None:
            raise ValueError()
        if isinstance(node, str):
            raise ValueError()

        # ast nodes parsing starts here
        elif isinstance(node, nodes.text.Text):
            report.texts.append(node)
            # replace arrows here, after HTML stuff has been parsed
            # not really a good idea, probably will cause conflicts
            return "%s" % node.value.replace('->', RIGHT_ARROW)

        if isinstance(node, mwparserfromhell.wikicode.Wikicode):
            return "".join(convert(n, strip, markup) for n in node.nodes)

        if isinstance(node, mwparserfromhell.nodes.extras.Parameter):
            return convert(node.value, strip, markup)

        # not supported, only used once in the manual
        if isinstance(node, nodes.argument.Argument):
            report.arguments.append(node)

        elif isinstance(node, nodes.comment.Comment):
            return COMMENT(node, "Comment: %s" % (node))

        elif isinstance(node, nodes.external_link.ExternalLink):
            report.external_links.append(node)
            if node.title:
                return remarkup('%s <%s>' % (convert(node.title, True, markup), convert(node.url, True, markup)), M_EXTLINK, markup)
            else:
                return convert(node.url, strip, markup)

        elif isinstance(node, nodes.heading.Heading):
            report.headings.append(node)
            title = node.title.strip()
            return "\n%s\n%s\n" % (title, TITLE_CHARS[node.level] * len(title))

        #--------------------------------------------------------
        #   HTML Entities (&gt; &nbsp; ...)
        #--------------------------------------------------------
        elif isinstance(node, nodes.html_entity.HTMLEntity):
            report.html_entities[node.value].append(node)

            if node.value == 'nbsp':
                return '\u00A0'
            if node.value == 'lt':
                return '<'
            elif node.value == 'gt':
                return '>'
            elif node.value == 'ndash':
                return '–'
            elif node.value == 'mdash':
                return '\u2014'
            if node.value == 'rarr':
                return RIGHT_ARROW
            elif node.value == 'amp':
                return '&'
            else:
                return FIXME(node, 'HTML Entity Unsupported %s' % node.value)

        #--------------------------------------------------------
        #   HTML Tags (<tag>contents</tag>)
        #--------------------------------------------------------
        elif isinstance(node, nodes.tag.Tag):
            report.html_tags[str(node.tag)].append(node)
            if str(node.tag) in TAG_TO_MARKUP:
                if strip:
                    return convert(node.contents, True, markup)
                else:
                    next_markup = TAG_TO_MARKUP[str(node.tag)]
                    return remarkup(convert(node.contents, strip, next_markup), next_markup, markup)
            if node.tag == 'dt':  # also matches ;
                # TODO
                # probably not necessary to deal with, <dt> is unused in the
                # wiki
                return EMPTY_STRING
            if node.tag == 'dd':  # also matches :
                if str(node) == ':':
                    return INDENTATION
                else:  # <dd>item</dd> - unused in the wiki
                    return '%s' % indent(convert(node.contents, strip, markup), INDENTATION)
            elif node.tag == 'br':
                return '\n'
            elif node.tag == 'hr':  # also matches ----
                return '┴----┴'
            elif node.tag == 'p':
                #<p>...</p> is ignored
                return convert(node.contents, strip, markup)
            elif node.tag == 'center':
                # rst does not support text alignment?
                return convert(node.contents, strip, markup)
            elif node.tag == 'gallery':
                # TODO <gallery> has additional options
                # width and height could be supported (but only occurs three times in the manual)
                # caption could be supported (but only occurs once)
                gallery_images = []
                for link in node.contents.strip().split('\n'):
                    gallery_images.append(
                        mwparserfromhell.parse('[[%s]]' % link.strip()))
                return '\n'.join(convert(img, True, markup) for img in gallery_images)

            elif node.tag == 'li':  # also matches # and *
                if node.contents is not None:
                    return FIXME(node, 'HTML lists not supported')
                else:
                    return "°"

            elif str(node.tag) in {'source', 'pre'}:
                return '::\n┴%s\n\n' % indent(convert(node.contents, strip, markup), INDENTATION)
            else:
                # TODO a couple of other HTML tags
                return FIXME(node, "Tag Unsupported:%s" % (node.tag))

        #--------------------------------------------------------
        #   Templates
        #--------------------------------------------------------
        elif isinstance(node, nodes.template.Template):
            name = node.name.strip().lower()
            report.templates[name].append(node)

            if name == 'clr':
                # TODO what is clr?
                return DELETE(node, "clr")

            elif name == 'literal':
                if strip:  # TODO warning?
                    return convert(node.params[0].value, True, markup)
                else:
                    # there are a couple of pointless {Literal|} in the manual
                    if node.params[0].strip() == EMPTY_STRING:
                        return EMPTY_STRING
                    return remarkup(convert(node.params[0], strip, M_GUILABEL), M_GUILABEL, markup)

            elif name == 'menu':
                if strip:
                    return "[%s]" % (' \u2192 '.join(convert(p.value, True, markup) for p in node.params))
                else:
                    return remarkup(' --> '.join(convert(p.value, True, M_MENU) for p in node.params), M_MENU, markup)

            elif name == 'note':
                if len(node.params) == 2:  # with title
                    return rst_admonition(name, convert(node.params[0], False, markup).strip(), [convert(node.params[1], False, markup)])
                else:  # without title
                    return rst_admonition(name, 'Note', [convert(node.params[0], False, markup)])

            elif name == 'nicetip':
                if len(node.params) == 2:  # with title
                    return rst_admonition(name, convert(node.params[0], False, markup).strip(), [convert(node.params[1], False, markup)])
                else:  # without title
                    return rst_admonition(name, 'Tip', [convert(node.params[0], False, markup)])
            elif name == 'warning/important':
                # this isnt really converting to RST well, body is outside of template:
                return rst_directive("warning", "", ["FIXME - warning body below"])

            elif name == 'page/header':
                return DELETE(node, "Template Page/Header")

            elif name == 'page/footer':
                return DELETE(node, "Template Page/Footer")

            elif name == 'refbox':
                name_to_index = {
                    'mode': 0, 'panel': 1, 'menu': 2, 'hotkey': 3, 'lang': 4}
                template = ['| Mode:     %s',
                            '| Panel:    %s',
                            '| Menu:     %s',
                            '| Hotkey:   %s',
                            EMPTY_STRING]
                template_args = [None] * len(template)
                for index, param in enumerate(node.params):
                    c = convert(param, False, markup).strip()
                    if param.showkey:  # argument by name
                        template_args[
                            name_to_index[str(param.name).lower().strip()]] = c
                    else:  # argument by index
                        template_args[index] = c

                body = []
                for ts, arg in zip(template, template_args):
                    if ts != EMPTY_STRING:
                        if arg is not None:
                            if arg != "":
                                body.append(ts % arg)
                return rst_admonition('refbox', 'Reference', body)

            elif name in {'review', 'wikitask/inprogress', 'wikitask/todo'}:
                return COMMENT(node, "TODO/Review: %s" % (node))

            elif name in {'shortcut', 'button'}:
                if strip:
                    return '[%s]' % (']['.join(convert(p.value, True, markup) for p in node.params))
                else:
                    return remarkup('-'.join(convert(p.value, True, M_KBD) for p in node.params), M_KBD, markup)

            elif name == 'abbr':
                if strip:
                    return '%s (%s)' % (convert(node.params[0], True, markup).strip(), node.params[1].strip())
                else:
                    return remarkup('%s (%s)' % (convert(node.params[0], True, M_ABBR).strip(), node.params[1].strip()), M_ABBR, markup)

            elif name == 'table':
                rows = []
                current_row = []
                rows.append(current_row)
                for param in node.params:
                    if param.showkey:
                        # this is an option for this row, ignored
                        # TODO
                        pass
                    else:
                        content = convert(param.value, False, markup).strip()
                        # see below
                        if content == 'IGNORE':
                            pass
                        # happens with '| a || b || c' syntax
                        elif content == '':
                            pass
                        elif content == '-':
                            # start new row, unless previous is empty
                            if current_row:
                                current_row = []
                                rows.append(current_row)
                        else:
                            current_row.append(content)

                return "\n%s\n" % rst_paint_table(rows)

            if name == 'css/prettytable':
                return 'IGNORE'

            # TODO a couple of other templates
            else:
                return FIXME(node, 'Template Unsupported: %s' % node.name)

        #--------------------------------------------------------
        #   Wiki Links (includes Doc,Image,File ...)
        #--------------------------------------------------------
        elif isinstance(node, nodes.wikilink.Wikilink):
            full_link = str(node.title)
            # some links have ':' prepended for some reason
            link_split = full_link.lstrip(':').split(':')
            namespace = None
            link_target = None
            if len(link_split) == 2:
                namespace = link_split[0].lower().strip()
                link_target = link_split[1].strip()
            else:
                return FIXME(node, "TODO: Internal Link")
            report.wikilinks[str(namespace)].append(node)
            options = {}

            caption = None
            text = node.text
            if text is not None:
                # mwparserfromhell doesn't bother parsing arguments for WikiLinks
                # the template argument parsing feature is reused instead
                ast = mwparserfromhell.parse("{{Dummy|%s}}" % text)
                # parse options, if any
                for param in ast.nodes[0].params:
                    # empty arg, like '[Namespace:Link|options|]'
                    if param.value is None:
                        continue
                    val_original = convert(param.value, strip, markup)
                    val = val_original.strip().lower()
                    if param.showkey:
                        key = param.name
                        if key == 'link':
                            pass
                        elif key == 'alt':
                            pass
                        elif key == 'page':
                            pass
                        elif key == 'class':
                            pass
                        elif key == 'lang':
                            pass
                        continue
                    else:
                        # like '512x256px' to specify both width and height
                        # not used, but no problem to have
                        m = re.match(r"(\d{1,6})x(\d{1,6})px", val)
                        if m is not None:
                            width, height = m.groups()
                            options['width'] = width
                            options['height'] = height
                            continue
                        else:
                            # like 'x256px' to specify height only
                            m = re.match(r'x(\d{1,6})px', val)
                            if m is not None:
                                options['height'] = m.groups(0)[0]
                                continue
                            # like '512px' or '512 px' to specify width only
                            else:
                                m = re.match(r'(\d{1,6})\s{0,1}px', val)
                                if m is not None:
                                    options['width'] = m.groups(0)[0]
                                    continue
                        if val == '':
                            pass
                        elif val in {'left', 'right', 'center', 'none'}:
                            if val != 'none':
                                if ENABLE_IMAGE_ALIGNMENT:
                                    options['align'] = val
                        elif val in {'baseline', 'sub', 'super', 'top', 'text-top', 'middle', 'bottom', 'text-bottom'}:
                            pass
                        elif val in {'border', 'frameless', 'frame', 'thumb'}:
                            pass
                        # this must be the caption (if we're at the last item)
                        # or some unrecognized/malformed parameter
                        else:
                            if caption is not None:
                                print(
                                    "WARNING: previous caption '%s' overwritten with '%s'" %
                                    (caption, val_original))
                            #caption = val_original
                            caption = convert(param.value, True, markup)
            # link conversion
            if namespace is None:
                # TODO Internal Links
                pass
            elif namespace == 'doc':  # TODO
                if caption is None:
                    return remarkup(wikipath_to_rstpath(link_target), M_DOC, markup)
                else:
                    return remarkup('%s <%s>' % (caption.strip(), wikipath_to_rstpath(link_target)), M_DOC, markup)

            elif namespace in {'file', 'image', 'media'}:
                if is_image_file(link_target):
                    # embed image
                    #header = "\n\n.. figure:: /images/%s" % (link_target.replace(" ", "_").replace(".PNG", ".jpg").replace(".png", ".jpg"))
                    header = "\n\n.. figure:: /images/%s" % (link_target.replace(" ", "_"))
                    body = []
                    if 'width' in options:
                        width = int(options['width'])
                        # could experiment with width/figwidth here
                        # same values seems to look best however
                        body.append(":width: %dpx" % width)
                        body.append(":figwidth: %dpx" % width)
                    if 'height' in options:
                        body.append(":height: %spx" % options['height'])
                    if 'align' in options:
                        body.append(":align: %s" % options['align'])
                    if caption is not None:
                        body.append(EMPTY_STRING)
                        body.append(caption.lstrip())
                    return "%s\n%s\n\n" % (header, indent('\n'.join(body), INDENTATION))
                else:
                    # create link to file on Wiki
                    if caption is None:
                        return remarkup("File:%s <%s>" % (link_target, wikiurl(full_link)), M_EXTLINK, markup)
                    else:  # TODO unmarked external links seem undesirable
                        return remarkup("%s <%s>" % (caption, wikiurl(full_link)), M_EXTLINK, markup)

            elif namespace == 'user':
                if caption is None:
                    return "`Wiki User:%s <%s>`__" % (link_target, wikiurl(full_link))
                else:  # TODO unmarked external links seem undesirable
                    return remarkup("%s <%s>" % (caption, wikiurl(full_link)), M_EXTLINK, markup)

            elif namespace == 'extensions':
                if caption is None:
                    return "`Extensions:%s <%s>`__" % (link_target, wikiurl(full_link))
                else:  # TODO unmarked external links seem undesirable
                    return remarkup("%s <%s>" % (caption, wikiurl(full_link)), M_EXTLINK, markup)

            elif namespace == 'category':
                # TODO?
                return DELETE(node, "Categories not supported")

            # TODO a few other namespaces
            elif namespace == 'help':
                pass

            return FIXME(node, "Link Type Unsupported: %s" % namespace)
        return FIXME(node, "Type Unsupported: %s" % type(node).__name__)
    return convert(start_node, False, None), report


def print_report(report, target):
    print("Conversion Report:\n", file=target)

    def print_summary(name, report_item):
        print(name + ':', file=target)
        total = 0
        for reason, issues in sorted(report_item.items()):
            count = len(issues)
            print("  %s: %d" % (reason, count), file=target)
            total += count
        print("\n  Total:%s\n" % total, file=target)

    print_summary("FIXME", report.fixme)
    print_summary("Deleted", report.deleted)
    print_summary("Templates used", report.templates)
    print_summary("HTML Entities", report.html_entities)
    print_summary("HTML Tags", report.html_tags)
    print_summary("Wiki Links", report.wikilinks)


def example_usage(mediawiki_string, output_file, report_file=None):
    rst_ast = mwparserfromhell.parse(preprocess(mediawiki_string))
    rst_pre, report = convert_mw(rst_ast)
    rst = postprocess(rst_pre)
    with open(output_file, "w+", encoding='utf-8') as f:
        f.write(rst)
    # Save a report only if a report_file is specified
    if report_file:
        with open(report_file, "w+", encoding='utf-8') as f:
            print_report(report, f)

# for use with multiprocess
def example_usage_mp(pair, report_file=None):
    example_usage(*pair, report_file=report_file)


if __name__ == "__main__":
    raise Exception("Call: blmw_to_rst_migrate.py")

