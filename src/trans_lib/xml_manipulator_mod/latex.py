import logging
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
        self.math_text_macros = {'text', 'mathrm'}

        if len(placeholder_commands) != 0:
            self.placeholder_commands.update(placeholder_commands)
        if len(placeholder_envs) != 0:
            self.placeholder_envs.update(placeholder_envs)
        if len(placeholders_with_text) != 0:
            self.math_text_macros.update(placeholders_with_text)
            
        
        # State attributes
        self.segments = []
        self.latex_content = ""

    def parse(self, latex_content):
        """Public method to start the parsing process."""
        self.segments = []
        self.latex_content = latex_content
        lw = LatexWalker(latex_content)
        nodelist, _, _ = lw.get_latex_nodes()
        self._walk_text_nodes(nodelist)
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
                if node.macroname in self.placeholder_commands:
                    self._add_placeholder(node.latex_verbatim())
                else:
                    self._add_placeholder(f"\\{node.macroname}{node.macro_post_space}")
                    if node.nodeargs:
                        for arg_node in node.nodeargs:
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

                    self._walk_text_nodes(node.nodelist)

                    end_placeholder = self.latex_content[content_end_pos:(node.pos + node.len)]
                    self._add_placeholder(end_placeholder)
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

def parse_latex(latex_content):
    """High-level function to instantiate and use the LatexParser."""
    parser = LatexParser()
    return parser.parse(latex_content)

def create_translation_xml(segments, output_dir: Path = Path("")):
    """
    Converts parsed segments into a single <TEXT> tag containing mixed content
    (text and <PH> tags), which is ideal for translation.

    - Merges consecutive non-text segments into single <PH> tags.
    - Creates one top-level <TEXT> tag.
    - Places text nodes and <PH> elements inside the <TEXT> tag.
    - Saves a mapping of placeholder IDs to their original content.

    Returns:
        tuple[str, dict]: A tuple containing the XML string and the placeholder dictionary.
    """
    # -- Step 1: Coalesce consecutive placeholders --
    # We group segments by their type. If consecutive segments are placeholders,
    # they will be grouped together and we can join their content.
    merged_segments = []
    for seg_type, group in groupby(segments, key=lambda x: x[0]):
        content_parts = [item[1] for item in group]
        if seg_type == 'text':
            # For text, we don't merge, we just add each part.
            # This preserves whitespace between text segments if any.
            for content in content_parts:
                merged_segments.append(('text', content))
        else:
            # For placeholders, we join the content of all consecutive items.
            merged_content = "".join(content_parts)
            if merged_content: # Only add if there's content
                 merged_segments.append(('placeholder', merged_content))


    # -- Step 2: Build the Mixed-Content XML --
    root = ET.Element('document')
    # All content will go inside a single <TEXT> tag
    text_container = ET.SubElement(root, 'TEXT')
    
    placeholders = {}
    ph_id = 1
    last_element = None # Keep track of the last <PH> element added

    for seg_type, content in merged_segments:
        if seg_type == 'text':
            if last_element is not None:
                # If text follows a <PH> tag, it becomes the .tail of that tag.
                last_element.tail = (last_element.tail or '') + content
            else:
                # If it's the first piece of text, it becomes the .text of the container.
                text_container.text = (text_container.text or '') + content
        
        elif seg_type == 'placeholder':
            # Create the placeholder element
            current_ph_id = str(ph_id)
            ph_elem = ET.SubElement(text_container, 'PH', id=current_ph_id, original=content)
            
            placeholders[current_ph_id] = content
            ph_id += 1
            last_element = ph_elem # This is now the most recent element

    # -- Step 3: Finalize and Save --
    # Use method='xml' and short_empty_elements=True for self-closing tags like <PH ... />
    xml_string = ET.tostring(root, encoding='unicode', method='xml', short_empty_elements=True)
    
    # Ensure the output directory exists
    # output_dir.mkdir(parents=True, exist_ok=True)

    return xml_string, placeholders
    
    # # Save placeholders for reconstruction
    # with open(output_dir / 'placeholders.json', 'w', encoding='utf-8') as f:
    #     json.dump(placeholders, f, indent=2, ensure_ascii=False)
        
    # return xml_string, placeholders

def latex_to_xml(source: str) -> tuple[str, dict]:
    return create_translation_xml(parse_latex(source))

def reconstruct_from_xml(translated_xml: str, placeholders: dict) -> str:
    """
    Rebuilds the source document from a translated XML file that uses a
    single <TEXT> tag with mixed content (text nodes and <PH> elements).

    This function correctly interprets the .text and .tail attributes of
    child elements within the <TEXT> tag to reconstruct the document in the
    correct order.

    Args:
        translated_xml (str): The XML string from the translation process.
                              It is expected to contain a <document><TEXT>...</TEXT></document> structure.
        placeholders (dict): The dictionary mapping placeholder IDs to their
                             original, non-translatable content.

    Returns:
        str: The fully reconstructed document with translated text and original placeholders.
    """
    try:
        root = ET.fromstring(translated_xml)
    except ET.ParseError as e:
        logging.error(f"Failed to parse translated XML: {e}")
        logging.error(f"XML Content that failed:\n{translated_xml}")
        raise

    # Find the main <TEXT> container tag.
    text_container = root.find('TEXT')
    if text_container is None:
        logging.warning("Could not find a <TEXT> tag in the provided XML. Returning an empty string.")
        return ""

    reconstructed_parts = []

    # 1. Start with the initial text of the <TEXT> tag itself.
    # This is the text before the very first <PH> child element.
    if text_container.text:
        reconstructed_parts.append(text_container.text)

    # 2. Iterate through all child elements (<PH> tags) within <TEXT>.
    for element in text_container:
        # A. Append the content of the placeholder itself.
        if element.tag == 'PH':
            ph_id = element.get('id')
            original_content = placeholders.get(ph_id)
            if original_content is not None:
                reconstructed_parts.append(original_content)
            else:
                # This could happen if the translator deleted a <PH> tag.
                logging.warning(f"Placeholder ID '{ph_id}' found in XML but not in the map. It will be skipped.")
        else:
            logging.warning(f"Unexpected tag <{element.tag}> found inside <TEXT>. It will be ignored.")

        # B. Append the text that immediately follows the placeholder.
        # This is the "tail" text of the element.
        if element.tail:
            reconstructed_parts.append(element.tail)

    return "".join(reconstructed_parts)
