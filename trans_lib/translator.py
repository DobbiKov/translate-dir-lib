import asyncio
import os
from pathlib import Path
from typing import Optional

from google import genai
from google.genai import types as g_types

from .constants import INTER_FILE_TRANSLATION_DELAY_SECONDS, DEFAULT_PROMPT_PATH

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

def _paste_vocabulary_into_prompt(prompt_template: str, vocabulary: str) -> str:
    return prompt_template.replace("[CUSTOM_VOCABULARY]", str(vocabulary))

async def _ask_gemini_model(full_prompt_message: str, model_name: str = "gemini-2.5-flash-preview-05-20") -> str:
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

        await asyncio.sleep(INTER_FILE_TRANSLATION_DELAY_SECONDS)
        response = client.models.generate_content(
                model=model_name,
                contents=contents
        )

        # print(f"DEBUG: Received from Gemini: {response.text[:200]}...") # Log response start
        
        return response.text or "" 
    
    except Exception as e:
        print(f"Error communicating with Gemini API: {e}")
        raise TranslationProcessError(f"Gemini API call failed: {e}", original_exception=e)

def finalize_prompt(prompt: str, contents_to_translate: str) -> str:
   return f"{prompt}\n<document>\n{contents_to_translate}\n</document>"

async def translate_chunk_with_prompt(prompt: str, chunk: str) -> str:
    """
    Translates the given chunk of text using the given prompt
    """
    final_message_to_model = finalize_prompt(prompt, chunk)
    
    translated_response_text = await _ask_gemini_model(final_message_to_model)
    
    return extract_translated_from_response(translated_response_text)


async def translate_chunk_async(text_chunk: str, target_language: Language) -> str:
    """Translates a single chunk of text asynchronously."""
    prompt_for_lang = _prepare_prompt_for_language(def_prompt_template, target_language)
    
    return await translate_chunk_with_prompt(prompt_for_lang, text_chunk)

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
            
    return "".join(translated_chunks)


