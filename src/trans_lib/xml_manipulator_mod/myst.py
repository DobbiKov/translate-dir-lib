from myst_parser.parsers.mdit import create_md_parser
from markdown_it.renderer import RendererProtocol
from markdown_it.utils import OptionsDict
from typing import Sequence, MutableMapping, Any, TypeAlias
from markdown_it.token import Token
from copy import deepcopy
from myst_parser.config.main import MdParserConfig

Chunk: TypeAlias = list[tuple[str, str]]

def _collect_handlers(cls):
    cls._handlers = {}
    for name, member in cls.__dict__.items():
        tokens = getattr(member, "_token_types", None)
        if tokens is not None:
            for token in tokens:
                cls._handlers[token] = member
    return cls

def _handler(token_type_s: str | list[str]):
    def decorator(fn):
        if isinstance(token_type_s, str):
            fn._token_types = [token_type_s]
        else:
            fn._token_types = token_type_s
        return fn
    return decorator

@_collect_handlers
class CustomRenderer(RendererProtocol):
    __output__ = "xml"
    _handlers = {}
    process_list = False

    # for content: cut the fields, and then parse content properly: for math and code

    def _dispatch(self, tokens: Sequence[Token], idx: int) -> tuple[Chunk, int]:
        """Route *tokens[idx]* to the appropriate renderer."""
        tok_type = tokens[idx].type
        handler = self._handlers.get(tok_type, CustomRenderer.renderUnknown)
        return handler(self, tokens, idx)

    @_handler(["colon_fence", "fence"])
    def renderColonFence(self, tokens: Sequence[Token], idx: int) -> tuple[Chunk, int]:
        token = tokens[idx]
        table_type = ""
        info = token.info
        content = token.content
        markup = token.markup

        table_type_end = info.find("}")
        if table_type_end != -1: # if there's such } then we need to extract fence type and then the title
            table_type = info[:table_type_end+1]
            if table_type_end + 1 == len(info):
                info = ""
            else:
                info = info[table_type_end+1:]
        match table_type:
            case "{eval-rst}":
                return [
                    ('placeholder', markup),
                    ('placeholder', table_type),
                    ('text', info),
                    ('placeholder', '\n'),
                    ('placeholder', content),
                    ('placeholder', '\n'),
                    ('placeholder', markup)
                ],  idx + 1
                
            case "{figure}" | "{image}" | "{iframe}" | "{embed}" | "{include}" | "{literalinclude}":
                content_parsed = parse_myst(content)
                return [
                    ('placeholder', markup),
                    ('placeholder', table_type),
                    ('placeholder', info),
                    ('placeholder', '\n'),
                    ] + content_parsed + [
                    ('placeholder', '\n'),
                    ('placeholder', markup),
                    ('placeholder', '\n'),
                ],  idx + 1

            case "{math}" | "{amsmath}": # TODO: handle math
                return [
                    ('placeholder', markup),
                    ('placeholder', table_type),
                    ('text', info),
                    ('placeholder', '\n'),
                    ('placeholder', content),
                    ('placeholder', '\n'),
                    ('placeholder', markup),
                    ('placeholder', '\n'),
                ],  idx + 1
            case "{code}" | "{code-block}" | "{sourcecode}" | "{code-cell}":
                # lang = info
                return [
                    ('placeholder', markup),
                    ('placeholder', table_type),
                    ('placeholder', info),
                    ('placeholder', '\n'),
                    ('placeholder', content), # TODO: handle code
                    ('placeholder', '\n'),
                    ('placeholder', markup),
                    ('placeholder', '\n'),
                ],  idx + 1
            case "{attention}" | "{caution}" | "{danger}" | "{error}" | "{hint}" | "{important}" | "{note}" | "{seealso}" | "{tip}" | "{warning}" | "{admonition}" | "{versionadded}" | "{versionchanged}" | "{deprecated}" | "{aside}" | "{sidebar}" | "{topic}" | "{dropdown}" | "{tab-set}" | "{toctree}" | "{table}" | "{list-table}":
                content_parsed = parse_myst(content)
                return [
                    ('placeholder', markup),
                    ('placeholder', table_type),
                    ('text', info),
                    ('placeholder', '\n'),
                ] + content_parsed + [
                    ('placeholder', '\n'),
                    ('placeholder', markup),
                    ('placeholder', '\n'),
                ],  idx + 1
            case _:
                return [
                    ('placeholder', markup),
                    ('placeholder', table_type),
                    ('placeholder', info),
                    ('placeholder', '\n'),
                    ('placeholder', content), 
                    ('placeholder', '\n'),
                    ('placeholder', markup),
                    ('placeholder', '\n'),
                ],  idx + 1
                

    @_handler("field_list_open")
    def renderFieldList(self, tokens: Sequence[Token], start_idx: int) -> tuple[Chunk, int]:
        end_idx = find_tag_id(tokens, "field_list_close", start_idx)
        if end_idx == -1:
            return [], start_idx + 1
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
            elif token_type == "field_list_close":
                res.append(('placeholder', '\n'))
            
            idx += 1
                
        return res, end_idx + 1

    @_handler("table_open")
    def renderMdTable(self, tokens: Sequence[Token], start_idx: int) -> tuple[Chunk, int]:
        end_idx = find_tag_id(tokens, "table_close", start_idx) 
        if end_idx == -1:
            return [], start_idx + 1
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
        return res, end_idx + 1   

    @_handler("link_open")
    def renderLink(self, tokens: Sequence[Token], start_idx: int) -> tuple[Chunk, int]:
        end_idx = find_tag_id(tokens, "link_close", start_idx)
        if end_idx == -1:
            return [], start_idx + 1

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
        ], end_idx + 1

    @_handler("footnote_reference_open")
    def renderFootnoteReference(self, tokens: Sequence[Token], start_idx: int) -> tuple[Chunk, int]:
        end_idx = find_tag_id(tokens, "footnote_reference_close", start_idx)
        if end_idx == -1:
            return [], start_idx + 1
        idx = start_idx

        label = ""
        text_tokens = []
        
        while idx <= end_idx:
            token = tokens[idx]
            if token.type == "footnote_reference_open":
                label = token.meta['label']
            elif token.type == "footnote_reference_close":
                pass
            else:
                text_tokens = text_tokens + self.renderToken(tokens, idx)[0]
            idx += 1
        return [
            ('placeholder', '['),
            ('placeholder', f'^{label}'),
            ('placeholder', ']'),
            ('placeholder', ': ')
        ] + text_tokens, end_idx + 1

        
    @_handler("inline")
    def renderInline(self, tokens: Sequence[Token], idx: int) -> tuple[Chunk, int]:
        token = tokens[idx]
        if token.children:
            return self.renderInlineChildren(token.children), idx + 1
        else:
            return [], idx + 1
    @_handler("heading_open")
    def renderHeading(self, tokens: Sequence[Token], idx: int) -> tuple[Chunk, int]:
        token = tokens[idx]
        token_markup = token.markup
        if token_markup == "=":
            token_markup = "#"
        if token_markup == "-":
            token_markup = "##"
        return [('placeholder', token_markup + " ")], idx + 1
         
    @_handler(["heading_close", "blockquote_close", "list_item_close"])
    def renderLineBrake(self, tokens: Sequence[Token], idx: int) -> tuple[Chunk, int]:
        return [('placeholder', "\n")], idx + 1

    @_handler(["paragraph_close", "softbreak", "hardbreak"])
    def renderBigLineBrake(self, tokens: Sequence[Token], idx: int) -> tuple[Chunk, int]:
        if not self.process_list:
            return [('placeholder', "\n\n")], idx + 1
        return [], idx + 1

    @_handler(["em_open", "em_close"])
    def renderEmphasize(self, tokens: Sequence[Token], idx: int) -> tuple[Chunk, int]:
        return [('placeholder', "*")], idx + 1

    @_handler(["strong_open", "strong_close"])
    def renderStrong(self, tokens: Sequence[Token], idx: int) -> tuple[Chunk, int]:
        return [('placeholder', "**")], idx + 1

    @_handler("text")
    def renderText(self, tokens: Sequence[Token], idx: int) -> tuple[Chunk, int]:
        token = tokens[idx]
        return [('text', token.content)], idx + 1

    @_handler("math_inline")
    def renderInlineMath(self, tokens: Sequence[Token], idx: int) -> tuple[Chunk, int]:
        token = tokens[idx]
        return [
            ('math', "$" + token.content + "$")
        ], idx + 1

    @_handler("math_inline_double")
    def renderDoubleInlineMath(self, tokens: Sequence[Token], idx: int) -> tuple[Chunk, int]:
        token = tokens[idx]
        return [
            ('math', "$$" + token.content + "$$")
        ], idx + 1

    @_handler("amsmath")
    def renderAmsmath(self, tokens: Sequence[Token], idx: int) -> tuple[Chunk, int]:
        token = tokens[idx]
        return [('math', token.content)], idx + 1

    @_handler("footnote_ref")
    def renderFootnoteRef(self, tokens: Sequence[Token], idx: int) -> tuple[Chunk, int]:
        token = tokens[idx]
        return [('placeholder', "[^" + token.meta["label"] + "]")], idx + 1

    @_handler("paragraph_open")
    def renderOpenParagraph(self, tokens: Sequence[Token], idx: int) -> tuple[Chunk, int]:
        return [], idx + 1
    @_handler("front_matter")
    def renderFrontMatter(self, tokens: Sequence[Token], idx: int) -> tuple[Chunk, int]:
        token = tokens[idx]
        return [('placeholder', f"---\n{token.content}\n---\n")], idx + 1
    @_handler("myst_target")
    def renderMystTarget(self, tokens: Sequence[Token], idx: int) -> tuple[Chunk, int]:
        token = tokens[idx]
        return [('placeholder', f"({token.content})=\n")], idx + 1
    @_handler("blockquote_open")
    def renderQuote(self, tokens: Sequence[Token], idx: int) -> tuple[Chunk, int]:
        return [('placeholder', "> ")], idx + 1
    @_handler("hr")
    def renderDelimiter(self, tokens: Sequence[Token], idx: int) -> tuple[Chunk, int]:
        return [('placeholder', "---\n")], idx + 1

    @_handler("myst_role")
    def renderRole(self, tokens: Sequence[Token], idx: int) -> tuple[Chunk, int]:
        token = tokens[idx]
        return [('placeholder', f"{{{token.meta["name"]}}}`{token.content}`")], idx + 1

    @_handler("code_inline")
    def renderInlineCode(self, tokens: Sequence[Token], idx: int) -> tuple[Chunk, int]:
        token = tokens[idx]
        return [('placeholder', f"`{token.content}`")], idx + 1

    @_handler("myst_block_break")
    def renderBlockBreak(self, tokens: Sequence[Token], idx: int) -> tuple[Chunk, int]:
        token = tokens[idx]
        return [('placeholder', f"+++ {token.content}\n")], idx + 1


        

    @_handler("myst_line_comment")
    def renderLineComment(self, tokens: Sequence[Token], idx: int) -> tuple[Chunk, int]:
        token = tokens[idx]
        return [
            ('placeholder', '% '),
            ('text', token.content),
            ('placeholder', '\n')
        ], idx + 1
        
    @_handler("bullet_list_open")
    def renderBulletList(self, tokens: Sequence[Token], idx: int) -> tuple[Chunk, int]:
        return self._renderBulletList(tokens, idx)
        # return [('placeholder', f"{{{token.meta["name"]}}}`{token.content}`")], idx + 1

    @_handler("html_inline")
    def renderHtmlInline(self, tokens: Sequence[Token], idx: int) -> tuple[Chunk, int]:
        token = tokens[idx]
        return [
            ('placeholder', token.content)
        ], idx + 1
        
    def _renderBulletList(self, tokens: Sequence[Token], idx: int, level: int = 0) -> tuple[Chunk, int]:
        res = []
        idx += 1
        while idx < len(tokens):
            token = tokens[idx]
            if token.type == "bullet_list_close":
                idx += 1
                break
            elif token.type == "bullet_list_open":
                self.process_list = True
                temp_res, new_idx = self._renderBulletList(tokens, idx, level+1)
                res = res + temp_res
                idx = new_idx
            elif token.type == "list_item_open":
                self.process_list = True
                cont = ("\t"*level) + "- "
                res.append(
                    ('placeholder', cont)
                )
                idx += 1
            else:
                temp_res, new_idx = self.renderToken(tokens, idx)
                res = res + temp_res
                idx = new_idx
        self.process_list = False
        return res, idx
                
                
        
    def renderUnknown(self, tokens: Sequence[Token], idx: int) -> tuple[Chunk, int]:
        token = tokens[idx]
        return [('unknown', token.content + "^^^" +token.type or f"[hank: {token.type}]")], idx + 1

    def renderToken(self, tokens: Sequence[Token], idx: int) -> tuple[list[tuple[str, str]], int]:
        return self._dispatch(tokens, idx)

    def renderInlineChildren(self, tokens: Sequence[Token]) -> list[tuple[str, str]]:
        res = []
        idx = 0
        while idx < len(tokens):
            temp_res, new_idx = self.renderToken(tokens, idx)
            res = res + temp_res
            idx = new_idx
        return res

    def render(self, tokens: Sequence[Token], options: OptionsDict, env: MutableMapping[str, Any]):
        res = []
        idx = 0
        while idx < len(tokens):
            temp_res, new_idx = self._dispatch(tokens, idx)
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
            # "linkify",
            "replacements",
            "smartquotes",
            "substitution",
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
