import logging
import re
import sys
from pathlib import Path

import metapub

logging.getLogger().setLevel(logging.WARNING)


BIB_PATH = Path(
    "/Users/philippaebischer/Documents/HRL/Knowledge/Literature/library/full_library.bib"
)


def norm_doi(s: str) -> str:
    s = s.strip()
    s = re.sub(r"(?i)^https?://(dx\.)?doi\.org/", "", s)
    s = re.sub(r"(?i)^doi:\s*", "", s)
    return s.strip().lower()


ENTRY_HEADER = re.compile(r"@[\w\-]+\s*{\s*([^,\s]+)\s*,", re.M)


DOI_FIELD = re.compile(r'(?im)^\s*doi\s*=\s*(\{([^}]*)\}|"([^"]*)")\s*,?\s*$')


def build_doi_to_key(bib_text: str) -> dict[str, str]:
    doi_to_key: dict[str, str] = {}

    parts = re.split(r"(?=@[\w\-]+\s*{)", bib_text)
    for part in parts:
        part = part.strip()
        if not part.startswith("@"):
            continue

        m_key = ENTRY_HEADER.search(part)
        if not m_key:
            continue
        key = m_key.group(1).strip()

        m_doi = DOI_FIELD.search(part)
        if not m_doi:
            continue
        doi_raw = (m_doi.group(2) or m_doi.group(3) or "").strip()
        if not doi_raw:
            continue

        doi = norm_doi(doi_raw)

        doi_to_key.setdefault(doi, key)

    return doi_to_key


def main():
    if not BIB_PATH.exists():
        print(f"ERROR: cannot find {BIB_PATH.resolve()}", file=sys.stderr)
        sys.exit(1)

    bib_text = BIB_PATH.read_text(encoding="utf-8", errors="replace")
    doi_to_key = build_doi_to_key(bib_text)

    input_pmids = sys.argv[1:]
    for pmid in input_pmids:
        doi = metapub.convert.pmid2doi(pmid)

        if doi is None:
            print(f"Unknown publication: pmid ?= {pmid}")
            continue

        doi = norm_doi(doi)
        key = doi_to_key.get(doi)
        if key:
            print(f"{pmid}\t{doi}\t{key}")
        else:
            print(
                f"not found in library\thttp://doi.org/{doi}\thttps://sci-hub.hlgczx.com/{doi}"
            )


if __name__ == "__main__":
    main()
