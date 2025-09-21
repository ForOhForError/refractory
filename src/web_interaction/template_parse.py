import html.parser
import re
import typing
from collections import OrderedDict
from html import unescape

"""
Everything in here is a bodge. Oh well.
Features parsing (some of) xml with regexes. Take that, zalgo post.
"""

DOUBLE_BRACE_SIMPLE_MATCH = re.compile(r"{{2,2}.*?}{2,2}")
REPLACEMENT_STRING = "A_VERY_LONG_STRING_USED_TO_REPLACE_DOUBLE_BRACES".lower()

VOID_ELEMENTS = [
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "source",
    "track",
    "wbr",
]


class Element:
    def __init__(
        self, tag=None, attrs=None, data=None, parent=None, end=False, start_end=False
    ):
        self.tag = tag
        self.attrs = attrs if attrs else OrderedDict()
        self.data = data
        self.children = []
        self.parent = parent
        self.end = end
        self.start_end = start_end
        self.ending_tag = None

    def set_ending_tag(self, ending_tag):
        self.ending_tag = ending_tag

    def clear(self):
        self.children.clear()

    def put_child(self, element, pos=None):
        element.parent = self
        if pos == None:
            pos = len(self.children)
        self.children.insert(pos, element)

    def attr_string(self):
        construct = ""
        for entry in self.attrs.items():
            key, value = entry
            add_space = len(construct) > 0 and not (key.startswith("/"))
            construct += f"{' ' if add_space else ''}"
            construct += (
                f'{key}="{self.attrs[key]}"' if self.attrs[key] != None else key
            )
        return construct

    def __str__(self):
        if self.data:
            return self.data
        elif self.tag:
            return f"<{'/' if self.end else ''}{self.tag}{' ' if self.attrs else ''}{self.attr_string()}{' /' if self.start_end else ''}>"
        else:
            return ""

    def reconstruct(self):
        recon = ""
        recon += str(self)
        for child in self.children:
            recon += child.reconstruct()
        if self.ending_tag:
            recon += self.ending_tag.reconstruct()
        return recon

    def search(
        self,
        tag: str,
        attr: typing.Dict[str, str],
        results: typing.List["Element"] = None,
        limit_matches=-1,
        limit_depth=None,
        _level=0,
    ):
        if results == None:
            results = []
        if limit_depth and _level > limit_depth:
            return results
        if self.tag == tag and all(
            [key in self.attrs and attr[key] in self.attrs[key] for key in attr]
        ):
            if limit_matches < 0 or len(results) < limit_matches:
                results.append(self)
        for ele in self.children:
            ele.search(
                tag,
                attr,
                results=results,
                limit_matches=limit_matches,
                limit_depth=limit_depth,
                _level=_level + 1,
            )
        return results


class TemplateOverwriter(html.parser.HTMLParser):
    def __init__(self, *, subject="", convert_charrefs=False):
        super().__init__(convert_charrefs=convert_charrefs)

    def feed(self, in_string):
        findings = DOUBLE_BRACE_SIMPLE_MATCH.findall(in_string)
        self.replacements += findings
        replaced = in_string
        for i in range(len(findings)):
            replaced = re.sub(
                DOUBLE_BRACE_SIMPLE_MATCH,
                f"{REPLACEMENT_STRING}_{i}_",
                replaced,
                count=1,
            )
        super().feed(replaced)

    def reset(self):
        self.root = Element()
        self.current = self.root
        self.replacements = []
        super().reset()

    @property
    def reconstructed(self):
        output = self.root.reconstruct()
        for i in range(len(self.replacements)):
            output = output.replace(
                f"{REPLACEMENT_STRING}_{i}_", self.replacements[i], 1
            )
        return output

    def fix_handlebar_attrs(self, attrs, attr_ranges=[]):
        text = self.get_starttag_text()
        new_attrs = OrderedDict()
        for ix in range(len(attrs)):
            key, value = attrs[ix]
            start, _ = attr_ranges[ix]
            if start > 0 and text[start - 1] != " ":  # fix keys starting with /
                key = text[start - 1] + key
            new_attrs[key] = value
        return new_attrs

    def handle_startendtag(self, tag, attrs, attr_ranges=[]):
        ordered_attrs = self.fix_handlebar_attrs(attrs, attr_ranges=attr_ranges)
        element = Element(tag=tag, attrs=ordered_attrs, start_end=True)
        self.current.put_child(element)

    def handle_starttag(self, tag, attrs, attr_ranges=[]):
        ordered_attrs = self.fix_handlebar_attrs(attrs, attr_ranges=attr_ranges)
        element = Element(tag=tag, attrs=ordered_attrs)
        self.current.put_child(element)
        if tag not in VOID_ELEMENTS:
            self.current = element

    def handle_endtag(self, tag):
        element = Element(tag=tag, end=True)
        self.current.set_ending_tag(element)
        if self.current.parent:
            self.current = self.current.parent

    def handle_charref(self, name):
        self.current.put_child(Element(data=name))

    def handle_entityref(self, name):
        self.current.put_child(Element(data=name))

    def handle_data(self, data):
        self.current.put_child(Element(data=data))

    def handle_comment(self, data):
        self.current.put_child(Element(data=data))

    def handle_decl(self, decl):
        self.current.put_child(Element(data=decl))

    def handle_pi(self, data):
        self.current.put_child(Element(data=data))

    def unknown_decl(self, data):
        self.current.put_child(Element(data=data))

    # slightly modified from python source, to pass attribute index ranges
    def parse_starttag(self, i):
        self._HTMLParser__starttag_text = None
        endpos = self.check_for_whole_start_tag(i)
        if endpos < 0:
            return endpos
        rawdata = self.rawdata
        self._HTMLParser__starttag_text = rawdata[i:endpos]

        # Now parse the data between i+1 and j into a tag and attrs
        attrs = []
        attr_ranges = []
        match = html.parser.tagfind_tolerant.match(rawdata, i + 1)
        assert match, "unexpected call to parse_starttag()"
        k = match.end()
        self.lasttag = tag = match.group(1).lower()
        while k < endpos:
            m = html.parser.attrfind_tolerant.match(rawdata, k)
            if not m:
                break
            attrname, rest, attrvalue = m.group(1, 2, 3)
            if not rest:
                attrvalue = None
            elif (
                attrvalue[:1] == "'" == attrvalue[-1:]
                or attrvalue[:1] == '"' == attrvalue[-1:]
            ):
                attrvalue = attrvalue[1:-1]
            if attrvalue:
                attrvalue = unescape(attrvalue)
            attrs.append((attrname.lower(), attrvalue))
            attr_ranges.append((m.start() - i, m.end() - i))
            k = m.end()

        end = rawdata[k:endpos].strip()
        if end not in (">", "/>"):
            self.handle_data(rawdata[i:endpos])
            return endpos
        if end.endswith("/>"):
            # XHTML-style empty tag: <span attr="value" />
            self.handle_startendtag(tag, attrs, attr_ranges=attr_ranges)
        else:
            self.handle_starttag(tag, attrs, attr_ranges=attr_ranges)
            if tag in self.CDATA_CONTENT_ELEMENTS:
                self.set_cdata_mode(tag)
        return endpos
