"""Compile reviewed UTF-8 PO catalogs into the MO files loaded by gettext."""
from pathlib import Path
import re

import polib

ROOT = Path(__file__).resolve().parents[1]


def compile_catalogs():
    for source in sorted((ROOT / "locales").glob("*/LC_MESSAGES/messages.po")):
        catalog = polib.pofile(str(source), check_for_duplicates=True)
        for entry in catalog:
            if entry.obsolete:
                continue
            if "fuzzy" in entry.flags or not entry.translated():
                raise ValueError(f"Unreviewed translation in {source}: {entry.msgid}")
            expected = sorted(re.findall(r"%\([a-zA-Z_][a-zA-Z_0-9]*\)[ds]", entry.msgid))
            for translation in entry.msgstr_plural.values() if entry.msgid_plural else [entry.msgstr]:
                actual = sorted(re.findall(r"%\([a-zA-Z_][a-zA-Z_0-9]*\)[ds]", translation))
                if actual != expected:
                    raise ValueError(f"Placeholder mismatch in {source}: {entry.msgid}")
        catalog.save_as_mofile(str(source.with_suffix(".mo")))
        print(f"Compiled {source.relative_to(ROOT)}")


if __name__ == "__main__":
    compile_catalogs()
