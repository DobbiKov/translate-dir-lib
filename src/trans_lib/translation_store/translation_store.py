from abc import ABC, abstractmethod
from pathlib import Path

from trans_lib.diff import get_best_match_in_dir, get_checksum_for_best_match_in_dir
from trans_lib.enums import Language
from trans_lib.translation_store.trans_db import ensure_db_dir, ensure_lang_dirs, find_correspondent_checksum, read_contents_by_checksum_with_lang, set_checksum_pair_to_correspondence_db, add_contents_to_db, do_translation_correspond_to_source

class TranslationStore(ABC):
    def __init__(self, root_path: Path, db_path: Path) -> None:
        self.db_path = db_path
        self.root_path = root_path
    @abstractmethod
    def lookup(self, src_checksum: str, src_lang: Language, tgt_lang: Language) -> str | None:
        pass

    @abstractmethod
    def persist_pair(
        self,
        src_checksum: str,
        tgt_checksum: str,
        src_lang: Language,
        tgt_lang: Language,
        src_text: str,
        tgt_text: str,
    ) -> None:
        """Return the cached *target text* if the pair exists, else *None*."""
        pass

    @abstractmethod
    def get_contents_by_checksum(self, checksum: str, lang: Language) -> str | None:
        pass

    @abstractmethod
    def get_best_pair_example_from_db(self, lang: Language, tgt_lang: Language, txt: str) -> tuple[str, str, float] | None:
        """
        Returns the triplet (src, tgt, score) of the best match between the provided text and the found source text in the database.
        """
        pass

    @abstractmethod
    def get_best_match_from_db(self, lang: Language, txt: str) -> tuple[str, float]:
        """
        Returns the best match and the score between the provided chunk and all the chunks of the provided language.
        """
        pass

    @abstractmethod
    def do_translation_correspond_to_source(self, root_path: Path, src_checksum: str, src_lang: Language, tgt_contents: str, tgt_lang: Language) -> bool:
        pass

class TranslationStoreCsv(TranslationStore):
    def __init__(self, root_path: Path) -> None:
        db_path = ensure_db_dir(root_path)
        super().__init__(root_path, db_path)

    def lookup(self, src_checksum: str, src_lang: Language, tgt_lang: Language) -> str | None:
        """Return the cached *target text* if the pair exists, else *None*."""
        tgt_checksum = find_correspondent_checksum(self.root_path, src_checksum, src_lang, tgt_lang)
        if tgt_checksum is None:
            return None
        return read_contents_by_checksum_with_lang(self.root_path, tgt_checksum, tgt_lang)

    def persist_pair(
        self,
        src_checksum: str,
        tgt_checksum: str,
        src_lang: Language,
        tgt_lang: Language,
        src_text: str,
        tgt_text: str,
    ) -> None:
        """
        Adds translation pair to the database
        """
        src_checksum = add_contents_to_db(self.root_path, src_text, src_lang) 
        tgt_checksum = add_contents_to_db(self.root_path, tgt_text, tgt_lang) 
        set_checksum_pair_to_correspondence_db(self.root_path, src_checksum, src_lang, tgt_checksum, tgt_lang)

    def get_best_pair_example_from_db(self, lang: Language, tgt_lang: Language, txt: str) -> tuple[str, str, float] | None:
        """
        Returns the triplet (src, tgt, score) of the best match between the provided text and the found source text in the database.
        """
        dir = ensure_lang_dirs(self.root_path, [lang])[0]
        src_checksum, score = get_checksum_for_best_match_in_dir(dir, txt)
        src = self.get_contents_by_checksum(src_checksum, lang)
        tgt = self.lookup(src_checksum, lang, tgt_lang)
        if tgt is None or src is None:
            return None
        return src, tgt, score

    def get_best_match_from_db(self, lang: Language, txt: str) -> tuple[str, float]:
        """
        Returns the best match and the score between the provided chunk and all the chunks of the provided language.
        """
        dir = ensure_lang_dirs(self.root_path, [lang])[0]
        return get_best_match_in_dir(dir, txt)

    def do_translation_correspond_to_source(self, root_path: Path, src_checksum: str, src_lang: Language, tgt_contents: str, tgt_lang: Language) -> bool:
        return do_translation_correspond_to_source(root_path, src_checksum, src_lang, tgt_contents, tgt_lang)

    def get_contents_by_checksum(self, checksum: str, lang: Language) -> str | None:
        return read_contents_by_checksum_with_lang(self.root_path, checksum, lang)
