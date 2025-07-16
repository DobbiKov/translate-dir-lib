import re
from pylatexenc.latexwalker import (LatexCommentNode, LatexWalker, LatexCharsNode, LatexMacroNode,
                                    LatexEnvironmentNode, LatexMathNode, LatexGroupNode)

class LatexParser:
    """
    Unified LaTeX parser that combines all functionality:
    - Asterisk preservation (\\section*, \\verb*, etc.)
    - Verb command preprocessing (\\verb|content|, \\verb*|content|)
    - Unknown commands with pipe delimiters (\\custommacro|content|)
    - Standard LaTeX argument parsing ({}, [])
    """
    
    def __init__(self, placeholder_commands: list = [], placeholder_envs: list = [], placeholders_with_text: list = []):
        # Configuration attributes
        self.placeholder_commands = {'ref', 'cite', 'label', 'includegraphics', 'input', 'include', 'frac', 'sqrt', 'path', 'url', 'href', '\\', 'verb'}
        self.placeholder_envs = {'verbatim', 'Verbatim', 'lstlisting', 'minted'}
        self.math_envs = {
                'equation', 'equation*', 'align', 'align*', 'aligned', 'gather', 'gather*', 
                'gathered', 'flalign', 'flalign*', 'alignat', 'alignat*', 'multline', 'multline*',
                'displaymath', 'math'
                }
        self.math_text_macros = {'text', 'mathrm'}
        self.definition_macros = {'newcommand', 'renewcommand', 'newenvironment', 'renewenvironment', 'def'}

        # Allow customization
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
        """
        Main parsing method that handles all special cases.
        Returns list of (type, content) tuples where type is 'text' or 'placeholder'.
        """
        # Extract verb commands first (highest priority) (causing the most problems ahah)
        verb_info = self._extract_verb_commands(latex_content)
        processed_content = verb_info['processed_text']
        
        # Extract unknown commands with pipe delimiters
        pipe_info = self._extract_pipe_commands(processed_content)
        processed_content = pipe_info['processed_text']
        
        # Parse with LaTeX parser
        self.segments = []
        self.latex_content = processed_content
        lw = LatexWalker(processed_content)
        nodelist, _, _ = lw.get_latex_nodes()

        if r'\end{document}' in processed_content and r'\begin{document}' not in processed_content:
            return [('placeholder', latex_content)]

        self._walk_text_nodes(nodelist)
        
        # Restore in reverse order (pipe commands first, then verb commands)
        self._restore_pipe_commands(pipe_info)
        self._restore_verb_commands(verb_info)
        
        return self.segments

    # === PREPROCESSING METHODS ===
    
    def _extract_verb_commands(self, text):
        """Extract \\verb and \\verb* commands to avoid parsing issues."""
        verb_commands = []
        
        verb_pattern = r'\\verb\*?(.)(.*?)\1'
        
        def collect_verb(match):
            verb_commands.append({
                'original': match.group(0),
                'start': match.start(),
                'end': match.end()
            })
            return f"VERBCMD{len(verb_commands)-1}VERBCMD"
        
        processed_text = re.sub(verb_pattern, collect_verb, text)
        
        return {
            'processed_text': processed_text,
            'verb_commands': verb_commands
        }
    
    def _extract_pipe_commands(self, text):
        """Extract unknown commands that use pipe delimiters \\command|content|."""
        pipe_commands = []
        
        # Pattern for commands with pipe delimiters (excluding verb which is handled separately)
        pipe_pattern = r'\\([a-zA-Z]+)(\*?)\|([^|]*)\|'
        
        def collect_pipe(match):
            command_name = match.group(1)
            star = match.group(2)
            content = match.group(3)
            
            # Skip verb commands as they're handled separately
            if command_name.lower() == 'verb':
                return match.group(0)
            
            pipe_commands.append({
                'original': match.group(0),
                'command': command_name,
                'star': star,
                'content': content,
                'start': match.start(),
                'end': match.end()
            })
            return f"PIPECMD{len(pipe_commands)-1}PIPECMD"
        
        processed_text = re.sub(pipe_pattern, collect_pipe, text)
        
        return {
            'processed_text': processed_text,
            'pipe_commands': pipe_commands
        }

    # === CORE PARSING METHODS ===
    
    def _add_placeholder(self, content):
        if content: 
            self.segments.append(('placeholder', content))

    def _add_text(self, content):
        if content.strip(): 
            self.segments.append(('text', content))
        elif content: 
            self.segments.append(('placeholder', content))

    def _process_chars_node(self, node):
        """Process character nodes, handling & specially."""
        parts = re.split(r'(&)', node.chars)
        for part in parts:
            if not part: 
                continue
            if part == '&': 
                self._add_placeholder(part)
            else: 
                self._add_text(part)

    def _walk_text_nodes(self, nodelist):
        """Main node walker for text mode - handles asterisk preservation."""
        if nodelist is None: 
            return

        for node in nodelist:
            if node.isNodeType(LatexCharsNode):
                self._process_chars_node(node)
            elif node.isNodeType(LatexCommentNode):
                self._add_placeholder('% ')
                self._add_text(node.comment)
                self._add_placeholder(node.comment_post_space)
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
                    # ASTERISK PRESERVATION: Use latex_verbatim() and extract command part
                    full_command = node.latex_verbatim()
                    if node.nodeargs:
                        # Find where the command ends and arguments begin
                        command_part = full_command
                        for arg_node in node.nodeargs:
                            if arg_node is not None:
                                arg_start = arg_node.pos - node.pos
                                command_part = full_command[:arg_start]
                                break
                        self._add_placeholder(command_part)
                        for arg_node in node.nodeargs:
                            if arg_node is None:
                                continue
                            self._walk_text_nodes([arg_node])
                    else:
                        # No arguments, use the full command
                        self._add_placeholder(full_command)
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
        """Process definition macros like \\newcommand with asterisk preservation."""
        # Extract command part from latex_verbatim to preserve asterisks
        full_command = node.latex_verbatim()
        if node.nodeargs:
            command_part = full_command
            for arg_node in node.nodeargs:
                if arg_node is not None:
                    arg_start = arg_node.pos - node.pos
                    command_part = full_command[:arg_start]
                    break
            self._add_placeholder(command_part)
        else:
            self._add_placeholder(full_command)
            
        if not node.nodeargs: 
            return

        syntax_args = node.nodeargs[:-1]
        definition_arg = node.nodeargs[-1]

        for arg in syntax_args:
            if arg is None:
                continue
            self._add_placeholder(arg.latex_verbatim())

        self._add_placeholder(definition_arg.delimiters[0])
        self._walk_definition_nodes(definition_arg.nodelist)
        self._add_placeholder(definition_arg.delimiters[1])

    def _walk_definition_nodes(self, nodelist):
        """Special walker for inside \\newcommand that recognizes # tokens."""
        if nodelist is None: 
            return
        for node in nodelist:
            if node.isNodeType(LatexMacroNode) and node.macroname == '#':
                self._add_placeholder(node.latex_verbatim())
            else:
                if node.isNodeType(LatexCharsNode): 
                    self._process_chars_node(node)
                elif node.isNodeType(LatexMathNode): 
                    self._add_placeholder(node.latex_verbatim())
                elif node.isNodeType(LatexGroupNode):
                    self._add_placeholder(node.delimiters[0])
                    self._walk_definition_nodes(node.nodelist)
                    self._add_placeholder(node.delimiters[1])
                elif node.isNodeType(LatexMacroNode):
                    self._walk_text_nodes([node])
                else:
                    self._add_placeholder(node.latex_verbatim())

    def _walk_math_nodes(self, nodelist):
        """Node walker for math mode with asterisk preservation."""
        if nodelist is None: 
            return
        for node in nodelist:
            if node.isNodeType(LatexMacroNode) and node.macroname in self.math_text_macros:
                # Extract command part to preserve asterisks
                full_command = node.latex_verbatim()
                if node.nodeargs:
                    command_part = full_command
                    for arg_node in node.nodeargs:
                        if arg_node is not None:
                            arg_start = arg_node.pos - node.pos
                            command_part = full_command[:arg_start]
                            break
                    self._add_placeholder(command_part)
                    for arg_node in node.nodeargs:
                        self._walk_text_nodes([arg_node])
                else:
                    self._add_placeholder(full_command)
            else:
                self._add_placeholder(node.latex_verbatim())

    # === POSTPROCESSING METHODS ===
    
    def _restore_pipe_commands(self, pipe_info):
        """Restore pipe delimited commands in the parsed segments."""
        for i, pipe_cmd in enumerate(pipe_info['pipe_commands']):
            placeholder = f"PIPECMD{i}PIPECMD"
            
            for j, (seg_type, content) in enumerate(self.segments):
                if placeholder in content:
                    if content.strip() == placeholder:
                        self.segments[j] = ('placeholder', pipe_cmd['original'])
                    else:
                        parts = content.split(placeholder)
                        if len(parts) == 2:
                            new_segments = []
                            if parts[0]:
                                new_segments.append(('text' if parts[0].strip() else 'placeholder', parts[0]))
                            
                            new_segments.append(('placeholder', pipe_cmd['original']))
                            
                            if parts[1]:
                                new_segments.append(('text' if parts[1].strip() else 'placeholder', parts[1]))
                            
                            self.segments[j:j+1] = new_segments
                            break

    def _restore_verb_commands(self, verb_info):
        """Restore verb commands in the parsed segments."""
        for i, verb_cmd in enumerate(verb_info['verb_commands']):
            placeholder = f"VERBCMD{i}VERBCMD"
            
            for j, (seg_type, content) in enumerate(self.segments):
                if placeholder in content:
                    if content.strip() == placeholder:
                        self.segments[j] = ('placeholder', verb_cmd['original'])
                    else:
                        parts = content.split(placeholder)
                        if len(parts) == 2:
                            new_segments = []
                            if parts[0]:
                                new_segments.append(('text' if parts[0].strip() else 'placeholder', parts[0]))
                            
                            new_segments.append(('placeholder', verb_cmd['original']))
                            
                            if parts[1]:
                                new_segments.append(('text' if parts[1].strip() else 'placeholder', parts[1]))
                            
                            self.segments[j:j+1] = new_segments
                            break

def parse_latex(latex_content) -> list[tuple[str, str]]:
    """High-level function to instantiate and use the LatexParser."""
    parser = LatexParser()
    return parser.parse(latex_content)


