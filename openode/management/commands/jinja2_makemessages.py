"""Jinja2's i18n functionality is not exactly the same as Django's.
In particular, the tags names and their syntax are different:

  1. The Django ``trans`` tag is replaced by a _() global.
  2. The Django ``blocktrans`` tag is called ``trans``.

(1) isn't an issue, since the whole ``makemessages`` process is based on
converting the template tags to ``_()`` calls. However, (2) means that
those Jinja2 ``trans`` tags will not be picked up my Django's
``makemessage`` command.

There aren't any nice solutions here. While Jinja2's i18n extension does
come with extraction capabilities built in, the code behind ``makemessages``
unfortunately isn't extensible, so we can:

  * Duplicate the command + code behind it.
  * Offer a separate command for Jinja2 extraction.
  * Try to get Django to offer hooks into makemessages().
  * Monkey-patch.

We are currently doing that last thing. It turns out there we are lucky
for once: It's simply a matter of extending two regular expressions.
Credit for the approach goes to:
http://stackoverflow.com/questions/2090717/getting-translation-strings-for-jinja2-templates-integrated-with-django-1-x
"""

# TODO this sctipt cannot recognize multirow jinja template variables, so all {{ VAR }} must be in one row!

import re
from cStringIO import StringIO
from django.core.management.commands import makemessages
from django.utils.translation import trans_real
from django.template import BLOCK_TAG_START, BLOCK_TAG_END, VARIABLE_TAG_START, VARIABLE_TAG_END

strip_whitespace_right = re.compile(r"(%s-?\s*(trans|pluralize).*?-%s)\s+" % (BLOCK_TAG_START, BLOCK_TAG_END), re.U)
strip_whitespace_left = re.compile(r"\s+(%s-\s*(endtrans|pluralize).*?-?%s)" % (BLOCK_TAG_START, BLOCK_TAG_END), re.U)

def strip_whitespaces(src):
    src = strip_whitespace_left.sub(r'\1', src)
    src = strip_whitespace_right.sub(r'\1', src)
    return src

class Command(makemessages.Command):

    def handle(self, *args, **options):
        old_endblock_re = trans_real.endblock_re
        old_block_re = trans_real.block_re
        old_templatize = trans_real.templatize
        # Extend the regular expressions that are used to detect
        # translation blocks with an "OR jinja-syntax" clause.
        trans_real.endblock_re = re.compile(
            trans_real.endblock_re.pattern + '|' + r"""^-?\s*endtrans\s*-?$""")
        trans_real.block_re = re.compile(
            trans_real.block_re.pattern + '|' + r"""^-?\s*trans(?:\s+(?!'|")(?=.*?=.*?)|-?$)""")
        trans_real.plural_re = re.compile(
            trans_real.plural_re.pattern + '|' + r"""^-?\s*pluralize(?:\s+.+|-?$)""")

        def my_templatize(src, origin=None):
            # Jinja2 spaceless
            src = strip_whitespaces(src)
            """
            Turns a Django template into something that is understood by xgettext. It
            does so by translating the Django translation tags into standard gettext
            function invocations.
            """
            from django.template import (Lexer, TOKEN_TEXT, TOKEN_VAR, TOKEN_BLOCK,
                    TOKEN_COMMENT, TRANSLATOR_COMMENT_MARK)
            out = StringIO()
            intrans = False
            inplural = False
            singular = []
            plural = []
            incomment = False
            comment = []
            for t in Lexer(src, origin).tokenize():
                if incomment:
                    if t.token_type == TOKEN_BLOCK and t.contents == 'endcomment':
                        content = ''.join(comment)
                        translators_comment_start = None
                        for lineno, line in enumerate(content.splitlines(True)):
                            if line.lstrip().startswith(TRANSLATOR_COMMENT_MARK):
                                translators_comment_start = lineno
                        for lineno, line in enumerate(content.splitlines(True)):
                            if translators_comment_start is not None and lineno >= translators_comment_start:
                                out.write(' # %s' % line)
                            else:
                                out.write(' #\n')
                        incomment = False
                        comment = []
                    else:
                        comment.append(t.contents)
                elif intrans:
                    if t.token_type == TOKEN_BLOCK:
                        endbmatch = trans_real.endblock_re.match(t.contents)
                        pluralmatch = trans_real.plural_re.match(t.contents)
                        if endbmatch:
                            if inplural:
                                out.write(' ngettext(%r,%r,count) ' % (''.join(singular), ''.join(plural)))
                                for part in singular:
                                    out.write(trans_real.blankout(part, 'S'))
                                for part in plural:
                                    out.write(trans_real.blankout(part, 'P'))
                            else:
                                out.write(' gettext(%r) ' % ''.join(singular))
                                for part in singular:
                                    out.write(trans_real.blankout(part, 'S'))
                            intrans = False
                            inplural = False
                            singular = []
                            plural = []
                        elif pluralmatch:
                            inplural = True
                        else:
                            filemsg = ''
                            if origin:
                                filemsg = 'file %s, ' % origin
                            raise SyntaxError("Translation blocks must not include other block tags: %s (%sline %d)" % (t.contents, filemsg, t.lineno))
                    elif t.token_type == TOKEN_VAR:
                        if inplural:
                            plural.append('%%(%s)s' % t.contents)
                        else:
                            singular.append('%%(%s)s' % t.contents)
                    elif t.token_type == TOKEN_TEXT:
                        contents = t.contents.replace('%', '%%')
                        if inplural:
                            plural.append(contents)
                        else:
                            singular.append(contents)
                else:
                    if t.token_type == TOKEN_BLOCK:
                        imatch = trans_real.inline_re.match(t.contents)
                        bmatch = trans_real.block_re.match(t.contents)
                        cmatches = trans_real.constant_re.findall(t.contents)
                        if imatch:
                            g = imatch.group(1)
                            if g[0] == '"': g = g.strip('"')
                            elif g[0] == "'": g = g.strip("'")
                            out.write(' gettext(%r) ' % g)
                        elif bmatch:
                            for fmatch in trans_real.constant_re.findall(t.contents):
                                out.write(' _(%s) ' % fmatch)
                            intrans = True
                            inplural = False
                            singular = []
                            plural = []
                        elif cmatches:
                            for cmatch in cmatches:
                                out.write(' _(%s) ' % cmatch)
                        elif t.contents == 'comment':
                            incomment = True
                        else:
                            out.write(trans_real.blankout(t.contents, 'B'))
                    elif t.token_type == TOKEN_VAR:
                        cmatches = trans_real.constant_re.findall(t.contents)
                        if cmatches:
                            for cmatch in cmatches:
                                out.write(' _(%s) ' % cmatch)
                        # findall is necessary for macros having translation constants as parameters
                        # original django code:
                        #
                        # parts = t.contents.split('|')
                        # cmatch = constant_re.match(parts[0])
                        # if cmatch:
                        #     out.write(' _(%s) ' % cmatch.group(1))
                        # for p in parts[1:]:
                        #     if p.find(':_(') >= 0:
                        #         out.write(' %s ' % p.split(':',1)[1])
                        #     else:
                        #         out.write(trans_real.blankout(p, 'F'))
                    elif t.token_type == TOKEN_COMMENT:
                        out.write(' # %s' % t.contents)
                    else:
                        out.write(trans_real.blankout(t.contents, 'X'))
            return out.getvalue()




        trans_real.templatize = my_templatize

        try:
            super(Command, self).handle(*args, **options)
        finally:
            trans_real.endblock_re = old_endblock_re
            trans_real.block_re = old_block_re
            trans_real.templatize = old_templatize
