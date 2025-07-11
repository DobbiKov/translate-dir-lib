from trans_lib.enums import ChunkType, DocumentType
from trans_lib.xml_manipulator_mod.code import CodeParser
from trans_lib.xml_manipulator_mod.latex import parse_latex
from trans_lib.xml_manipulator_mod.xml import create_translation_xml

def chunk_to_xml(source: str, doc_type: DocumentType, chunk_type: ChunkType) -> str:
    """
    Takes a chunk and the document type and returns the XML tagged version of the chunk
    """
    match doc_type:
        case DocumentType.LaTeX:
            return latex_to_xml(source)[0]
        case DocumentType.JupyterNotebook:
            return latex_to_xml(source)[0]
        case _:
            raise RuntimeError("Not implemented yet")

def latex_to_xml(source: str) -> tuple[str, dict]:
    return create_translation_xml(parse_latex(source))
def code_to_xml(source: str, language) -> tuple[str, dict]:
    """
    Main function that takes a code and the language it is written in and returns an XML for translating.
    """
    parser = CodeParser(language=language)
    segments = parser.parse(source)
    return create_translation_xml(segments)
