import html.parser

from collections import OrderedDict
from html import unescape

import re

DOUBLE_BRACE_SIMPLE_MATCH = re.compile(r"{{2,2}.*?}{2,2}")
REPLACEMENT_STRING = "A_VERY_LONG_STRING_USED_TO_REPLACE_DOUBLE_BRACES".lower()

class Element:
    def __init__(self, tag=None, attrs=None, data=None, parent=None, end=False, start_end=False):
        self.tag = tag
        self.attrs = attrs if attrs else OrderedDict()
        self.data = data
        self.children = []
        self.parent = parent
        self.end = end
        self.start_end = start_end

    def put_child(self, element):
        element.parent = self
        self.children.append(element)

    def attr_string(self):
        construct = ""
        for entry in self.attrs.items():
            key, value = entry
            add_space = len(construct) > 0 and not(key.startswith("/"))
            construct += f'{" " if add_space else ""}'
            construct += f'{key}="{self.attrs[key]}"' if self.attrs[key]!=None else key
        return construct

    def __str__(self):
        if self.data:
            return self.data
        elif self.tag:
            return f'<{"/" if self.end else ""}{self.tag}{" " if self.attrs else ""}{self.attr_string()}{" /" if self.start_end else ""}>'
        else:
            return ""

    def reconstruct(self):
        recon = ""
        recon += str(self)
        for child in self.children:
            recon += child.reconstruct()
        return recon

class TemplateOverwriter(html.parser.HTMLParser):
    def __init__(self, *, subject="", convert_charrefs=False):
        super().__init__(convert_charrefs=convert_charrefs)

    def feed(self, in_string):
        findings = DOUBLE_BRACE_SIMPLE_MATCH.findall(in_string)
        self.replacements += findings
        replaced = in_string
        for i in range(len(findings)):
            replaced = re.sub(DOUBLE_BRACE_SIMPLE_MATCH, f"{REPLACEMENT_STRING}_{i}_", replaced, count=1)
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
            output = output.replace(f"{REPLACEMENT_STRING}_{i}_", self.replacements[i], 1)
        return output

    def fix_handlebar_attrs(self, attrs):
        text = self.get_starttag_text()
        new_attrs = OrderedDict()
        for entry in attrs:
            key, value = entry
            ix = text.find(key)
            if ix > 0 and text[ix-1] != " ":
                key = text[ix-1]+key
            new_attrs[key] = value
        return new_attrs

    def handle_startendtag(self, tag, attrs):
        ordered_attrs = self.fix_handlebar_attrs(attrs)
        element = Element(tag=tag, attrs=ordered_attrs, start_end=True)
        self.current.put_child(element)

    def handle_starttag(self, tag, attrs):
        ordered_attrs = self.fix_handlebar_attrs(attrs)
        element = Element(tag=tag, attrs=ordered_attrs)
        self.current.put_child(element)
        self.current = element

    def handle_endtag(self, tag):
        element = Element(tag=tag, end=True)
        self.current.put_child(element)
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
        sself.current.put_child(Element(data=data))

    def unknown_decl(self, data):
        self.current.put_child(Element(data=data))
