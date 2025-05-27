import asyncio
import os
from pathlib import Path
from typing import Optional

from google import genai
from google.genai import types as g_types

from .enums import Language
from .helpers import divide_into_chunks, extract_translated_from_response, read_string_from_file
from .errors import TranslationProcessError


# TODO:
# Configure the API key
try:
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    if not GOOGLE_API_KEY:
        print("Warning: GOOGLE_API_KEY environment variable not set. Translation will fail.")
        # raise EnvironmentError("GOOGLE_API_KEY environment variable must be set for translation.")
except Exception as e:
    print(f"Error configuring Google GenAI: {e}")
    # This might happen if os.getenv itself fails or configure has issues not related to API key.


DEFAULT_PROMPT_PATH = Path("/Users/dobbikov/Desktop/stage/prompts/prompt4") # Make this configurable

def get_default_prompt_text() -> str:
    """Reads the default prompt text from the configured path."""
    try:
        return read_string_from_file(DEFAULT_PROMPT_PATH)
    except Exception as e:
        print(f"Warning: Could not load default prompt from {DEFAULT_PROMPT_PATH}: {e}. Using a fallback.")
        # Fallback prompt to avoid complete failure if file is missing
        return "Translate the following document to [TARGET_LANGUAGE]. Maintain the original structure and formatting as much as possible. Only output the translated document text inside <output> tags.\nDocument text:\n"


def_prompt_template = get_default_prompt_text()


def _prepare_prompt_for_language(prompt_template: str, target_language: Language) -> str:
    """Replaces the language placeholder in the prompt."""
    return prompt_template.replace("[TARGET_LANGUAGE]", str(target_language))


async def _ask_gemini_model(full_prompt_message: str, model_name: str = "gemini-2.0-flash") -> str:
    """
    Asks the Gemini model for a translation.
    The default model_name is "gemini-2.0-flash"
    """
    if not GOOGLE_API_KEY: # Re-check in case it wasn't set at module load
        raise EnvironmentError("GOOGLE_API_KEY environment variable must be set for translation.")

    client = genai.Client(api_key=GOOGLE_API_KEY)

    try:
        contents = g_types.Content(
                role='user',
                parts=[g_types.Part.from_text(text=full_prompt_message)]
        )
        

        # print(f"DEBUG: Sending to Gemini: {full_prompt_message[:200]}...") # Log request start

        response = client.models.generate_content(
                model=model_name,
                contents=contents
        )

        # print(f"DEBUG: Received from Gemini: {response.text[:200]}...") # Log response start
        
        return response.text or "" 
    
    except Exception as e:
        print(f"Error communicating with Gemini API: {e}")
        raise TranslationProcessError(f"Gemini API call failed: {e}", original_exception=e)


async def translate_chunk_async(text_chunk: str, target_language: Language) -> str:
    """Translates a single chunk of text asynchronously."""
    prompt_for_lang = _prepare_prompt_for_language(def_prompt_template, target_language)
    
    final_message_to_model = f"{prompt_for_lang}\n<document>\n{text_chunk}\n</document>"
    
    translated_response_text = await _ask_gemini_model(final_message_to_model)
    
    return extract_translated_from_response(translated_response_text)


async def translate_contents_async(contents: str, target_language: Language, lines_per_chunk: int = 50) -> str:
    """
    Translates the given string contents asynchronously, handling chunking.
    Includes a delay between chunk translations for rate limiting.
    """
    if not contents.strip():
        return ""

    chunks = divide_into_chunks(contents, lines_per_chunk)
    translated_chunks: list[str] = []

    # Rate limiting: Delay between chunks
    # The Rust code had sleep(5) inside ask_gemini_model (for each chunk indirectly)
    # and then an additional sleep(8) in translate_file_helper (after each file).
    # This suggests a need for delays.
    INTER_CHUNK_DELAY_SECONDS = 5 # Corresponds to the sleep in ask_gemini_model

    for i, chunk in enumerate(chunks):
        if not chunk.strip(): # Skip empty chunks
            translated_chunks.append(chunk) # Preserve empty lines if they form a chunk
            continue

        translated_chunk = await translate_chunk_async(chunk, target_language)
        translated_chunks.append(translated_chunk)
        
        if i < len(chunks) - 1: # If not the last chunk
            print(f"Translated chunk {i+1}/{len(chunks)}. Waiting for {INTER_CHUNK_DELAY_SECONDS}s...")
            await asyncio.sleep(INTER_CHUNK_DELAY_SECONDS)
            
    return "".join(translated_chunks)


async def translate_file_async(source_path: Path, target_language: Language) -> str:
    """Reads a file, translates its content asynchronously, and returns the translated content."""
    file_contents = read_string_from_file(source_path)
    return await translate_contents_async(file_contents, target_language)


async def translate_file_to_file_async(
    source_path: Path,
    target_path: Path,
    target_language: Language
) -> None:
    """Translates a file and writes the result to another file asynchronously."""
    translated_content = await translate_file_async(source_path, target_language)
    
    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(translated_content, encoding="utf-8")
    except IOError as e:
        raise TranslationProcessError(f"Failed to write translated file {target_path}: {e}", original_exception=e)
