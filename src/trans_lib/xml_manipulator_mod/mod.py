from trans_lib.enums import ChunkType, DocumentType
from trans_lib.xml_manipulator_mod.code import CodeParser
from trans_lib.xml_manipulator_mod.latex import parse_latex
from trans_lib.xml_manipulator_mod.myst import parse_myst
from trans_lib.xml_manipulator_mod.xml import create_translation_xml

def chunk_to_xml(source: str, chunk_type: ChunkType) -> str:
    """
    Takes a chunk and the document type and returns the XML tagged version of the chunk
    """
    match chunk_type:
        case ChunkType.LaTeX:
            return latex_to_xml(source)[0]
        case ChunkType.Myst:
            return myst_to_xml(source)[0]
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

def myst_to_xml(source: str) -> tuple[str, dict]:
    segments = parse_myst(source)
    def handle_segment(segment: tuple[str, str]) -> tuple[str, str]:
        if segment[0] == "math":
            return ('placeholder', segment[1]) # temporary | TODO: handle math
        return segment
    segments = [handle_segment(segment) for segment in segments]
    return create_translation_xml(segments)
