import re
from pylatexenc.latexwalker import (LatexWalker, LatexCharsNode, LatexMacroNode,
                                    LatexEnvironmentNode, LatexMathNode, LatexGroupNode)

import xml.etree.ElementTree as ET
from itertools import groupby
from pathlib import Path



class LatexParser:
    """
    Parses LaTeX content using a context-aware, recursive walker. It uses the
    parser's positional information and node lengths to robustly segment the document.
    """
    def __init__(self, placeholder_commands: list = [], placeholder_envs: list = [], placeholders_with_text: list = []):
        # Configuration attributes
        self.placeholder_commands = {'ref', 'cite', 'label', 'includegraphics', 'input', 'include', 'frac', 'sqrt', 'path', 'url', 'href', 'footnote', '\\'}
        self.placeholder_envs = {'verbatim', 'Verbatim', 'lstlisting'}
        self.math_envs = {
                'equation', 'equation*', 'align', 'align*', 'aligned', 'gather', 'gather*', 
                'gathered', 'flalign', 'flalign*', 'alignat', 'alignat*', 'multline', 'multline*',
                'displaymath', 'math'
                }
        self.math_text_macros = {'text', 'mathrm'}
        self.definition_macros = {'newcommand', 'renewcommand', 'newenvironment', 'renewenvironment', 'def'}

        if len(placeholder_commands) != 0:
            self.placeholder_commands.update(placeholder_commands)
        if len(placeholder_envs) != 0:
            self.placeholder_envs.update(placeholder_envs)
        if len(placeholders_with_text) != 0:
            self.math_text_macros.update(placeholders_with_text)


        # State attributes
        self.segments = []
        self.latex_content = ""

    def parse(self, latex_content) -> list[tuple[str, str]]:
        """Public method to start the parsing process."""
        self.segments = []
        self.latex_content = latex_content
        lw = LatexWalker(latex_content)
        nodelist, _, _ = lw.get_latex_nodes()

        if r'\end{document}' in latex_content and r'\begin{document}' not in latex_content:
            return [('placeholder', latex_content)]

        self._walk_text_nodes(nodelist)
        # list[tuple[txt, txt]] the list of tuples (type: placeholder or text, contents)
        return self.segments

    def _add_placeholder(self, content):
        if content: self.segments.append(('placeholder', content))

    def _add_text(self, content):
        if content.strip(): self.segments.append(('text', content))
        elif content: self.segments.append(('placeholder', content))

    def _process_chars_node(self, node):
        parts = re.split(r'(&)', node.chars)
        for part in parts:
            if not part: continue
            if part == '&': self._add_placeholder(part)
            else: self._add_text(part)

    def _walk_text_nodes(self, nodelist):
        """Recursively processes nodes in 'text' mode."""
        if nodelist is None: return

        for node in nodelist:
            if node.isNodeType(LatexCharsNode):
                self._process_chars_node(node)
            elif node.isNodeType(LatexMathNode):
                self._add_placeholder(node.delimiters[0])
                self._walk_math_nodes(node.nodelist)
                self._add_placeholder(node.delimiters[1])
            elif node.isNodeType(LatexGroupNode):
                self._add_placeholder('{')
                self._walk_text_nodes(node.nodelist)
                self._add_placeholder('}')
            elif node.isNodeType(LatexMacroNode):
                if node.macroname in self.definition_macros:
                    self._process_definition_macro(node)
                elif node.macroname in self.placeholder_commands:
                    self._add_placeholder(node.latex_verbatim())
                else:
                    self._add_placeholder(f"\\{node.macroname}{node.macro_post_space}")
                    if node.nodeargs:
                        for arg_node in node.nodeargs:
                            if arg_node is None:
                                continue
                            self._walk_text_nodes([arg_node])
            elif node.isNodeType(LatexEnvironmentNode):
                envname = node.environmentname
                if envname in self.placeholder_envs:
                    self._add_placeholder(node.latex_verbatim())
                else:
                    if not node.nodelist:
                        self._add_placeholder(node.latex_verbatim())
                        continue

                    content_start_pos = node.nodelist[0].pos
                    last_node = node.nodelist[-1]
                    content_end_pos = last_node.pos + last_node.len

                    begin_placeholder = self.latex_content[node.pos:content_start_pos]
                    self._add_placeholder(begin_placeholder)

                    if envname in self.math_envs:
                        self._walk_math_nodes(node.nodelist) 
                    else:
                        self._walk_text_nodes(node.nodelist)

                    end_placeholder = self.latex_content[content_end_pos:(node.pos + node.len)]
                    self._add_placeholder(end_placeholder)
            else:
                self._add_placeholder(node.latex_verbatim())
    def _process_definition_macro(self, node):
        """Processes macros like \newcommand by preserving syntax args and parsing the definition."""
        self._add_placeholder(f"\\{node.macroname}{node.macro_post_space}")
        if not node.nodeargs: return

        # The last argument is the definition body, the others are syntax.
        syntax_args = node.nodeargs[:-1]
        definition_arg = node.nodeargs[-1]

        for arg in syntax_args:
            if arg is None:
                continue
            # Preserve syntax arguments verbatim. This correctly handles {} and [].
            self._add_placeholder(arg.latex_verbatim())

        # For the definition body, parse it with the special definition walker.
        self._add_placeholder(definition_arg.delimiters[0])
        self._walk_definition_nodes(definition_arg.nodelist)
        self._add_placeholder(definition_arg.delimiters[1])

    def _walk_definition_nodes(self, nodelist):
        """A special walker for inside \newcommand, etc. that recognizes '#' tokens."""
        if nodelist is None: return
        for node in nodelist:
            if node.isNodeType(LatexMacroNode) and node.macroname == '#':
                self._add_placeholder(node.latex_verbatim())
            else:
                # Other than '#', the content is like regular text.
                # We can reuse the main walkers, being careful to avoid infinite recursion.
                # A simple way is to just call the relevant processing methods directly.
                if node.isNodeType(LatexCharsNode): self._process_chars_node(node)
                elif node.isNodeType(LatexMathNode): self._add_placeholder(node.latex_verbatim()) # Keep math in definitions simple
                elif node.isNodeType(LatexGroupNode):
                    self._add_placeholder(node.delimiters[0])
                    self._walk_definition_nodes(node.nodelist) # Recurse with this walker
                    self._add_placeholder(node.delimiters[1])
                elif node.isNodeType(LatexMacroNode):
                     # Recurse using the main text walker for nested commands like \textbf
                    self._walk_text_nodes([node])
                else:
                    self._add_placeholder(node.latex_verbatim())

    def _walk_math_nodes(self, nodelist):
        """Recursively processes nodes in 'math' mode."""
        if nodelist is None: return
        for node in nodelist:
            if node.isNodeType(LatexMacroNode) and node.macroname in self.math_text_macros:
                self._add_placeholder(f"\\{node.macroname}")
                if node.nodeargs:
                    for arg_node in node.nodeargs:
                        self._walk_text_nodes([arg_node])
            else:
                self._add_placeholder(node.latex_verbatim())

def parse_latex(latex_content) -> list[tuple[str, str]]:
    """High-level function to instantiate and use the LatexParser."""
    parser = LatexParser()
    return parser.parse(latex_content)


