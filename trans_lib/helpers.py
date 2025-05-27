import os
from pathlib import Path
from typing import List, Optional, Iterable

def find_file_upwards(start_path: Path, file_name: str) -> Optional[Path]:
    """
    Search the given directory and each parent directory for `file_name`.
    Returns the full path to the first match, or `None` if nothing is found.
    """
    current_dir = start_path.resolve()
    if not current_dir.is_dir():
        current_dir = current_dir.parent

    while current_dir:
        candidate = current_dir / file_name
        if candidate.is_file():
            return candidate
        
        if current_dir == current_dir.parent:  # Reached filesystem root
            break
        current_dir = current_dir.parent
    
    return None

def divide_into_chunks(text: str, lines_per_chunk: int) -> List[str]:
    """
    Takes a text, divides it into chunks (each chunk containing at most
    `lines_per_chunk` number of lines) and returns the list of such chunks.
    """
    if not text or lines_per_chunk <= 0:
        return [text] if text else []

    lines = text.splitlines(keepends=True) # keepends=True to preserve newline chars
    if not lines: # Handle empty string or string with no newlines if splitlines returns empty
        return [text] if text.strip() else []


    chunks: List[str] = []
    current_chunk_lines: List[str] = []
    
    for i, line in enumerate(lines):
        current_chunk_lines.append(line)
        if (i + 1) % lines_per_chunk == 0:
            chunks.append("".join(current_chunk_lines))
            current_chunk_lines = []
            
    if current_chunk_lines:
        chunks.append("".join(current_chunk_lines))
        
    # If original text had no newlines but lines_per_chunk > 0
    if not chunks and text:
        return [text]

    return chunks


def extract_text_between_tags(text: str, start_tag: str, end_tag: str) -> str:
    """
    Extracts content between the first occurrence of start_tag and its corresponding end_tag.
    Handles nested tags superficially by finding the first start and then the first end.
    Rust version was specific to <output>
    """
    start_index = text.find(start_tag)
    if start_index == -1:
        return ""
    
    start_index += len(start_tag)
    
    end_index = text.find(end_tag, start_index)
    if end_index == -1:
        # If end_tag is not found after start_tag, maybe return content till end or empty
        return text[start_index:] # Or "" if strict matching is needed

    return text[start_index:end_index].strip()

def extract_translated_from_response(message: str) -> str:
    """
    Takes a text and returns the content written within all <output>...</output> tags.
    Concatenates content from multiple <output> tags if present.
    """
    
    if "<output>" not in message:
        return "" 

    res_list = []
    current_pos = 0
    while True:
        start_idx = message.find("<output>", current_pos)
        if start_idx == -1:
            break
        start_idx += len("<output>")
        
        end_idx = message.find("</output>", start_idx)
        if end_idx == -1: # No closing tag found for the last opened <output>
            # Decide behavior: take rest of string, or ignore this segment.
            # Rust logic: `chunk_string.split("</output>").next().unwrap()`
            # This would take the part before `</output>` if it exists.
            # If `</output>` doesn't exist in `chunk_string`, `split` returns a single element list,
            # and `.next().unwrap()` takes that whole `chunk_string`.
            # So, if no closing tag, it takes the rest of that segment.
            segment = message[start_idx:]
            if segment.startswith("\n"): # Mimic strip_prefix
                 segment = segment[1:]
            res_list.append(segment)
            break # No more closing tags to look for

        segment = message[start_idx:end_idx]
        if segment.startswith("\n"): # Mimic strip_prefix
            segment = segment[1:]
        res_list.append(segment)
        current_pos = end_idx + len("</output>")
        
    return "".join(res_list)


def read_string_from_file(path: Path) -> str:
    """Reads file and returns its contents in String format."""
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise
    except Exception as e:
        raise IOError(f"Could not read file {path}: {e}") from e
