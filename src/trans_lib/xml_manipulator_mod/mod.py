from itertools import groupby
import logging
import xml.etree.ElementTree as ET

from trans_lib.enums import DocumentType
from trans_lib.xml_manipulator_mod.latex import parse_latex

def reconstruct_from_xml(translated_xml: str) -> str:
    """
    Rebuilds the source document from a translated XML file that uses a
    single <TEXT> tag with mixed content (text nodes and <PH> elements).

    This function correctly interprets the .text and .tail attributes of
    child elements within the <TEXT> tag to reconstruct the document in the
    correct order.

    Args:
        translated_xml (str): The XML string from the translation process.
                              It is expected to contain a <document><TEXT>...</TEXT></document> structure.
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
            try:
                orig = element.get('original') # if the id isn't found in the PH's db, we get the source from the 'original' attribute
                if orig is None:
                    logging.warning(f"Original contents of the <PH> tag is not found!")
                else:
                    reconstructed_parts.append(orig)
            except Exception as e:
                logging.warning(f"Original contents of the <PH> tag is not found!")
        else:
            logging.warning(f"Unexpected tag <{element.tag}> found inside <TEXT>. It will be ignored.")

        # B. Append the text that immediately follows the placeholder.
        # This is the "tail" text of the element.
        if element.tail:
            reconstructed_parts.append(element.tail)

    return "".join(reconstructed_parts)


def create_translation_xml(segments: list[tuple[str, str]]) -> tuple[str, dict]:
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

def chunk_to_xml(source: str, doc_type: DocumentType) -> str:
    """
    Takes a chunk and the document type and returns the XML tagged version of the chunk
    """
    match doc_type:
        case DocumentType.LaTeX:
            return latex_to_xml(source)[0]
        case _:
            raise RuntimeError("Not implemented yet")

def latex_to_xml(source: str) -> tuple[str, dict]:
    return create_translation_xml(parse_latex(source))
