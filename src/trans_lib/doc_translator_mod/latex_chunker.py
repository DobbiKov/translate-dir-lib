import re
from pylatexenc.latexwalker import LatexWalker, LatexCharsNode, LatexMacroNode, LatexGroupNode, LatexEnvironmentNode, LatexCommentNode, LatexMathNode, LatexSpecialsNode
from typing import Any, Optional
from pathlib import Path

def _get_node_full_span(node: Any, original_latex_string: str) -> tuple[int, int]:
    """
    Calculates the full character span (start_pos, end_pos) of a LaTeX node,
    including its arguments if it's a macro or environment.
    """
    start_pos = node.pos
    end_pos = node.pos + node.len

    if isinstance(node, LatexMacroNode):
        if node.nodeargd is not None and node.nodeargd.argnlist:
            last_arg_node = node.nodeargd.argnlist[-1]
            if last_arg_node is not None:
                end_pos = last_arg_node.pos + last_arg_node.len
    
    # Ensure the calculated end_pos doesn't exceed the document length
    end_pos = min(end_pos, len(original_latex_string))
    
    return start_pos, end_pos

def _chunk_nodelist(
    nodelist: list[Any],
    original_latex_string: str,
    base_start_offset: int, # The starting character offset in original_latex_string for this nodelist's domain
    end_offset_limit: int # The ending character offset for this nodelist's domain (e.g., before \end{document})
) -> list[str]:
    """
    Recursively chunks a given pylatexenc nodelist, respecting full spans of
    environments and macros with arguments.
    `base_start_offset` is the starting character offset of the segment of the original
    string that this nodelist represents (e.g., the content inside \begin{document}).
    `end_offset_limit` is the character offset where this nodelist's content ends
    (e.g., just before \end{document} macro).
    """
    chunks_raw: list[str] = []
    current_chunk_start_pos = base_start_offset
    
    between_nodes = []

    i = 0
    while i < len(nodelist):
        node = nodelist[i]
        
        # Calculate node's actual start/end in the original string
        node_full_span_start, node_full_span_end = _get_node_full_span(node, original_latex_string)

        # Ensure we don't process beyond the limit for this nodelist's domain
        if node_full_span_start >= end_offset_limit:
            break 

        # Handle Any raw text (e.g., paragraphs) that comes *before* the current node
        if node_full_span_start > current_chunk_start_pos:
            raw_text_before = original_latex_string[current_chunk_start_pos : node_full_span_start]
            paragraphs = re.split(r'\n\s*\n+', raw_text_before)
            for para in paragraphs:
                if para.strip():
                    chunks_raw.append(para.strip())
            
        current_chunk_start_pos = node_full_span_start

        # Process the current node based on its type to form a new chunk
        
        if isinstance(node, LatexEnvironmentNode): # we include the \begin{...} ... \end{...}
            if len(between_nodes) != 0: # if between_nodes is not empty, then there were contents between environments
                chunks_raw.append("".join(between_nodes))
                between_nodes = []
                
            chunk_content = original_latex_string[node_full_span_start:node_full_span_end].strip()
            if chunk_content: chunks_raw.append(chunk_content)
            current_chunk_start_pos = node_full_span_end
            i += 1
            
        elif isinstance(node, LatexMacroNode) and node.nodeargd is not None and node.nodeargd.argnlist:
            if len(between_nodes) != 0: # if between_nodes is not empty, then there were contents between environments
                chunks_raw.append("".join(between_nodes))
                between_nodes = []
                
            chunk_content = original_latex_string[node_full_span_start:node_full_span_end].strip()
            if chunk_content: chunks_raw.append(chunk_content)
            current_chunk_start_pos = node_full_span_end
            i += 1

        else:
            chunk_content = original_latex_string[node_full_span_start:node_full_span_end]
            if chunk_content: # add chunk to between nodes
                between_nodes.append(chunk_content)
            current_chunk_start_pos = node_full_span_end
            i += 1

    if len(between_nodes) != 0: # if between_nodes is not empty, then there were contents after all the environments
        chunks_raw.append("".join(between_nodes))
        between_nodes = []   
    return chunks_raw



def split_latex_document_into_chunks(latex_document_string: str) -> list[dict[str, Any]]:
    """
    Splits a full LaTeX document into chunks, including a dedicated
    preamble chunk and chunking of the document body.
    """
    lw = LatexWalker(latex_document_string)
    full_nodelist, _, _ = lw.get_latex_nodes()

    all_chunks: list[dict[str, Any]] = []
    
    document_env_node: Optional[LatexEnvironmentNode] = None
    
    # Find the \begin{document} environment node
    for node in full_nodelist:
        if isinstance(node, LatexEnvironmentNode) and node.environmentname == 'document':
            document_env_node = node
            break

    if document_env_node is not None: # if the document contains begin document
        BEGIN_DOC_MACRO_LEN = len(r'\begin{document}')
        END_DOC_MACRO_LEN = len(r'\end{document}')

        # Handle Preamble Chunk 
        preamble_end_pos = document_env_node.pos # This is where \begin{document} starts
        preamble_content = latex_document_string[0:preamble_end_pos].strip()
        if preamble_content:
            all_chunks.append({
                "id": "preamble_001",
                "content": preamble_content,
                "chunk_type": "preamble"
            })
        # the pos is never None as well as len because the document_env_node is not None, it's done for the linter
        if document_env_node.pos is None:
            document_env_node.pos = 0
        if document_env_node.len is None:
            document_env_node.len = 0
        
        # Add \begin{document} macro as its own chunk 
        begin_doc_raw = latex_document_string[document_env_node.pos : document_env_node.pos + BEGIN_DOC_MACRO_LEN].strip()
        if begin_doc_raw:
            all_chunks.append({
                "id": "begin_document_macro",
                "content": begin_doc_raw,
                "chunk_type": "macro_declaration"
            })

        # Process the Document Body
        doc_body_start_pos = document_env_node.pos + BEGIN_DOC_MACRO_LEN
        
        # The body ends just before \end{document}
        doc_body_end_pos = (document_env_node.pos + document_env_node.len) - END_DOC_MACRO_LEN
        
        if document_env_node.nodelist:
            doc_body_chunks = _chunk_nodelist(
                document_env_node.nodelist,
                latex_document_string,
                base_start_offset=doc_body_start_pos,
                end_offset_limit=doc_body_end_pos
            )
            for chunk_content in doc_body_chunks:
                all_chunks.append({
                    "id": f"doc_body_{len(all_chunks)}",
                    "content": chunk_content,
                    "chunk_type": "content"
                })

        # Add \end{document} macro as its own chunk
        end_doc_raw = latex_document_string[doc_body_end_pos : doc_body_end_pos + END_DOC_MACRO_LEN].strip()
        if end_doc_raw:
            all_chunks.append({
                "id": "end_document_macro",
                "content": end_doc_raw,
                "chunk_type": "macro_declaration"
            })
            
    else:
        # If no \begin{document} found, apply the chunking to the whole nodelist.
        # print("Warning: No \\begin{document} environment found. Chunking entire document as main body.")
        doc_chunks = _chunk_nodelist(
            full_nodelist,
            latex_document_string,
            base_start_offset=0,
            end_offset_limit=len(latex_document_string)
        )
        for chunk_content in doc_chunks:
            all_chunks.append({
                "id": f"auto_chunk_{len(all_chunks)}",
                "content": chunk_content,
                "chunk_type": "content"
            })

    # Add common metadata to all chunks
    for i, chunk in enumerate(all_chunks):
        if not chunk.get("id"):
            chunk["id"] = f"auto_chunk_{i+1}"


    return all_chunks


# reading chunks
def _parse_metadata_block(block_str: str) -> dict[str, str]:
    """Parses a LaTeX comment metadata block string into a dictionary."""
    metadata = {}
    lines = block_str.splitlines()
    for line in lines:
        line = line.strip()
        if line.startswith('%'):
            line = line[1:].strip() # Remove the comment char
            if line.startswith('--- CHUNK_METADATA_START ---') or \
               line.startswith('--- CHUNK_METADATA_END ---'):
                continue # Skip the delimiters
            
            if ':' in line:
                key, value = line.split(':', 1) # Split only on first column
                metadata[key.strip()] = value.strip()
    return metadata

def read_chunks_with_metadata_from_latex(
    filepath: Path 
) -> list[dict]:
    """
    Reads a LaTeX file containing metadata blocks and splits it into chunks.
    Returns a list of dictionaries, each with 'source' and 'metadata' keys.
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        full_content = f.read()

    chunks_data: list[dict] = []
    
    METADATA_BLOCK_REGEX = re.compile(
        r'(?s)(% --- CHUNK_METADATA_START ---\n.*?\n% --- CHUNK_METADATA_END ---\n)'
    )

    parts = METADATA_BLOCK_REGEX.split(full_content)

    current_chunk_content = ""
    current_metadata: dict[str, str] = {}

    start_index = 0
    if not parts[0].strip():
        start_index = 1
        # If the file starts with metadata, parts[1] will be the first metadata block
        if len(parts) > 1:
            current_metadata = _parse_metadata_block(parts[1])
            start_index = 2 # Start processing content from here

    for i in range(start_index, len(parts)):
        part = parts[i]
        
        if i % 2 == 1: # This is a metadata block (odd index)
            # Store the previous chunk's data if we had content
            if current_chunk_content.strip():
                chunks_data.append({
                    "source": current_chunk_content.strip(),
                    **current_metadata # Unpack current_metadata into the dict
                })
            current_metadata = _parse_metadata_block(part)
            current_chunk_content = "" # Reset content for the new chunk
        else: # This is a content block (even index)
            current_chunk_content += part

    # Add the very last chunk's data if there's any accumulated content
    if current_chunk_content.strip():
        chunks_data.append({
            "source": current_chunk_content.strip(),
            **current_metadata
        })

    return chunks_data
