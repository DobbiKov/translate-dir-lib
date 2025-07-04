from pprint import pprint
from markdown_it import MarkdownIt

from myst_parser.parsers.mdit import create_md_parser
from markdown_it.renderer import RendererProtocol
from markdown_it.utils import OptionsDict, OptionsType
from typing import Sequence, MutableMapping, Any
from markdown_it.token import Token
from copy import deepcopy
from myst_parser.config.main import MdParserConfig


class CustomRenderer(RendererProtocol):
    __output__ = "xml"
    def renderColonFence(self, tokens: Sequence[Token], idx: int) -> list[tuple[str, str]]:
        token = tokens[idx]
        table_type = ""
        info = token.info
        content = token.content

        table_type_end = info.find("}")
        if table_type_end != -1: # if there's such } then we need to extract fence type and then the title
            table_type = info[:table_type_end+1]
            if table_type_end + 1 == len(info):
                info = ""
            else:
                info = info[table_type_end+1:]
        content_parsed = parse_myst(content)
        return [
            ('placeholder', ':::'),
            ('placeholder', table_type),
            ('text', info),
            ('placeholder', '\n'),
        ] + content_parsed + [
            ('placeholder', '\n'),
            ('placeholder', ':::')
        ]
    def renderFieldList(self, tokens: Sequence[Token], start_idx: int, end_idx: int) -> list[tuple[str, str]]:
        res = []
        idx = start_idx
        
        line = "" # string that collects a line of the field list from multiple tokens
        
        while idx <= end_idx:
            token = tokens[idx]
            token_type = token.type
            if token_type == "fieldlist_body_close":
                line += "\n"
                res.append(('placeholder', line))
                line = ""
            elif token_type in ["fieldlist_name_open", "fieldlist_name_close"]:
                line += ":"
            elif token_type == "inline":
                line += token.content
            
            idx += 1
                
        return res
    def renderMdTable(self, tokens: Sequence[Token], start_idx: int, end_idx: int) -> list[tuple[str, str]]:
        res = []
        table = interprete_table(tokens, start_idx, end_idx)

        # header elements
        res.append(('placeholder', '|'))
        for elem in table['header']:
            res.append(('text', elem['content']))
            res.append(('placeholder', '|'))
        res.append(('placeholder', '\n'))

        # lines after header
        res.append(('placeholder', '|'))
        for elem in table['header']:
            if elem.get("align") is None:
                res.append(('placeholder', '---'))
            else:
                match elem["align"]:
                    case "left":
                        res.append(('placeholder', ':---'))
                    case "center":
                        res.append(('placeholder', ':---:'))
                    case "right":
                        res.append(('placeholder', '---:'))
            
            res.append(('placeholder', '|'))
        res.append(('placeholder', '\n'))

        # elements
        for line in table['lines']:
            res.append(('placeholder', '|'))
            for elem in line:
                res.append(('text', elem))
                res.append(('placeholder', '|'))
            res.append(('placeholder', '\n'))
        return res   
    def renderLink(self, tokens: Sequence[Token], start_idx: int, end_idx: int) -> list[tuple[str, str]]:
        res = []
        idx = start_idx

        href = ""
        text_tokens = []
        
        while idx <= end_idx:
            token = tokens[idx]
            if token.type == "link_open":
                href = token.attrs['href']
            elif token.type == "link_close":
                pass
            else:
                text_tokens = text_tokens + self.renderToken(tokens, idx)[0]
            idx += 1
        return [
            ('placeholder', '['),
        ] + text_tokens + [
            ('placeholder', ']'),
            ('placeholder', f'({href})')
        ]
        
    def renderToken(self, tokens: Sequence[Token], idx: int) -> tuple[list[tuple[str, str]], int]:
        token = tokens[idx]
        if token.type == "inline" and token.children:
            return self.renderInline(token.children), idx + 1
        elif token.type == "field_list_open":
            end_idx = find_tag_id(tokens, "field_list_close")
            if end_idx == -1:
                return [], idx + 1
            return self.renderFieldList(tokens, idx, end_idx), end_idx + 1
        elif token.type == "table_open":
            end_idx = find_tag_id(tokens, "table_close", idx)
            if end_idx == -1:
                return [], idx + 1
            return self.renderMdTable(tokens, idx, end_idx), end_idx + 1
        elif token.type == "link_open":
            end_idx = find_tag_id(tokens, "link_close", idx)
            if end_idx == -1:
                return [], idx + 1
            return self.renderLink(tokens, idx, end_idx), end_idx + 1
        elif token.type == "heading_open":
            token_markup = token.markup
            if token_markup == "=":
                token_markup = "#"
            if token_markup == "-":
                token_markup = "##"
            return [('placeholder', token_markup + " ")], idx + 1
        elif token.type in ["heading_close", "paragraph_open", "paragraph_close", "softbreak"]:
            return [('placeholder', "\n")], idx + 1
        elif token.type in ["em_open", "em_close"]:
            return [('placeholder', "*")], idx + 1
        elif token.type == "text":
            return [('text', token.content)], idx + 1
        elif token.type in ["math_inline"]:
            return [
                ('math', "$" + token.content + "$")
            ], idx + 1
        elif token.type in ["math_inline_double"]:
            return [
                ('math', "$$" + token.content + "$$")
            ], idx + 1
        elif token.type in ["amsmath"]:
            return [('math', token.content)], idx + 1
        elif token.type in ["footnote_ref"]:
            return [('placeholder', "[^" + token.meta["label"] + "]")], idx + 1
        elif token.type in ["colon_fence"]:
            return self.renderColonFence(tokens, idx), idx + 1
        return [('unknown', token.content + "^^^" +token.type or f"[hank: {token.type}]")], idx + 1
    def renderInline(self, tokens: Sequence[Token]) -> list[tuple[str, str]]:
        res = []
        idx = 0
        while idx < len(tokens):
            temp_res, new_idx = self.renderToken(tokens, idx)
            res = res + temp_res
            idx = new_idx
        return res
    def render(self, tokens: Sequence[Token], options: OptionsDict, env: MutableMapping[str, any]):
        res = []
        idx = 0
        while idx < len(tokens):
            temp_res, new_idx = self.renderToken(tokens, idx)
            res = res + temp_res
            idx = new_idx
        return res

def find_tag_id(tokens: Sequence[Token], token_type: str, start_id: int = 0) -> int:
    """
    Looks for the first occurence of the token of the provided type `tag` in the provided sequence of Tokens.
    Start from the first token in the sequence, or from the provided one (optional argument).

    Returns:
        id in the list of the first occurence or -1 if there's no such occurence
    """
    curr = start_id
    while curr < len(tokens):
        token = tokens[curr]
        if token.type == token_type:
            return curr
        curr += 1
    
    return -1

def interprete_table(tokens: Sequence[Token], start_idx: int, end_idx: int) -> dict:
    """
    Takes tokens of a table and interpretes it into more convenient format.

    Returns:
        {
            header: list[{content, style}],
            lines: list[list[str]]
        }
    """
    header = [] # {content: str, align: str}
    lines = []
    line = []
    idx = start_idx

    head_closed = False

    curr_style = None

    # attrs={'style': 'text-align:right'}
    # tr_close
    while idx <= end_idx:
        token = tokens[idx]
        token_type = token.type
        if token_type == "thead_close":
            head_closed = True
            header = deepcopy(line)
            line = []
        elif head_closed and token_type == 'tr_close':
            lines.append(deepcopy(line))
            line = []
        elif token_type == "th_open" and token.attrs.get('style') is not None:
            curr_style = token.attrs['style']
        elif token_type == "inline":
            if head_closed:
                line.append(token.content)
            else: # head is not closed
                style = None
                if curr_style is not None:
                    match curr_style:
                        case 'text-align:right':
                            style = "right"
                        case 'text-align:left':
                            style = "left"
                        case _: 
                            style = "center"
                    curr_style = None
                element = {'content': token.content}
                if style is not None:
                    element['align'] = style
                line.append(element)
                
        
        idx += 1
    return {'header': header, 'lines': lines}

def parse_myst(source: str) -> list[tuple[str, str]]:
    cfg = MdParserConfig(                   
        enable_extensions=set([
            "amsmath",
            "attrs_block",
            "attrs_inline",
            "colon_fence",
            "deflist",
            "dollarmath",
            "fieldlist",
            "html_admonition",
            "html_image",
            "linkify",
            "replacements",
            "smartquotes",
            "substitution",
            "tasklist"
        ]),  
        dmath_allow_labels = True,
        dmath_allow_space = True,
        dmath_allow_digits = True,
        dmath_double_inline = True,
    )
    # parser = create_md_parser(cfg, renderer=lambda md: RendererHTML(md))
    parser = create_md_parser(cfg, renderer=lambda md: CustomRenderer())
    parser.options["sourceMap"] = True
    opt_dict = OptionsDict({    
        "maxNesting": 20,
        "html": True,
        "linkify": False,
        "typographer": True,
        "quotes": '“”‘’',
        "xhtmlOut": False,
        "breaks": True,
        "langPrefix": "language-",
        "highlight": None 
    })

    return parser.render(source, opt_dict)
