import enum
from typing import List

class Language(str, enum.Enum):
    """Enumeration for supported languages."""
    FRENCH = "French"
    ENGLISH = "English"
    GERMAN = "German"
    SPANISH = "Spanish"
    UKRAINIAN = "Ukrainian"

    def get_dir_suffix(self) -> str:
        """Returns the directory suffix for the language."""
        if self == Language.FRENCH:
            return "_fr"
        elif self == Language.ENGLISH:
            return "_en"
        elif self == Language.GERMAN:
            return "_de"
        elif self == Language.SPANISH:
            return "_es" # Note: Rust code had "_sp", common is "_es" for Spanish
        elif self == Language.UKRAINIAN:
            return "_ua"
        # Should not happen with enum
        raise ValueError(f"Unknown language: {self}")

    @classmethod
    def from_str(cls, s: str) -> 'Language':
        for lang_member in cls:
            if lang_member.value.lower() == s.lower():
                return lang_member
        raise ValueError(f"'{s}' is not a valid Language")

    def __str__(self) -> str:
        return self.value


CLI_LANGUAGE_CHOICES: List[str] = [lang.value for lang in Language]

class DocumentType(str, enum.Enum):
    """
    Enumeration for the document types
    """
    JupyterNotebook = "jupyter"
    Markdown = "markdown"
    LaTeX = "latex"
    Other = "other"

class ChunkType(str, enum.Enum):
    Myst = "myst"
    Code = "code"
    LaTeX = "latex"
    Other = "other"
