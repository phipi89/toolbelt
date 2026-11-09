import os
import re
import sys
from argparse import ArgumentParser

import requests
from bs4 import BeautifulSoup
from tabulate import tabulate

DEFAULT_LANGUAGE = "deen"
DICTCC_URLS = {
    "deen": "https://www.dict.cc/",
    "defr": "https://defr.dict.cc/",
    "deit": "https://deit.dict.cc/",
}
USER_AGENT = "toolbelt-dictionary/1.0 (personal interactive lookup)"
DIRECTIONS = {
    "ten": ("deen", "de", ["German", "English"]),
    "fen": ("deen", "en", ["English", "German"]),
    "tfr": ("defr", "de", ["German", "French"]),
    "ffr": ("defr", "fr", ["French", "German"]),
    "tit": ("deit", "de", ["German", "Italian"]),
    "fit": ("deit", "it", ["Italian", "German"]),
}
COMPACT_MAX_ENTRIES = 6


class TranslateError(Exception):
    pass


def fetch_dictcc(word, language=DEFAULT_LANGUAGE, verbose=False):
    url = DICTCC_URLS[language]
    if verbose:
        print(f"Requesting {url} s={word!r}", file=sys.stderr)
    try:
        response = requests.get(
            url,
            params={"s": word},
            headers={"User-Agent": USER_AGENT},
            timeout=15,
        )
    except requests.RequestException as error:
        raise TranslateError(f"dict.cc request failed: {error}") from error
    if not response.ok:
        raise TranslateError(f"dict.cc returned HTTP {response.status_code}")
    return response.content


def parse_dictcc_response(html, source_lang="de"):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = " ".join(soup.get_text(" ").split())
    title = soup.title.get_text(strip=True) if soup.title else ""
    if "don't run crawlers" in text.lower() or re.fullmatch(
        r"just a moment[.!…\s]*", title, flags=re.IGNORECASE
    ):
        raise TranslateError(
            "dict.cc blocked the request; try the lookup in your browser"
        )
    content = soup.find(id="maincontent")
    if content is None or content.find("input", id="sinp") is None:
        raise TranslateError(
            "dict.cc returned an unrecognized page instead of dictionary results"
        )

    rows = []
    seen = set()
    word_class = ""
    sections = {
        "verben": "verb",
        "verbs": "verb",
        "substantive": "noun",
        "nouns": "noun",
        "adjektive": "adjective",
        "adjectives": "adjective",
        "adverbien": "adverb",
        "adverbs": "adverb",
    }
    for entry in content.find_all("tr"):
        heading = entry.find("td", class_="td6", recursive=False)
        if heading is not None:
            label = heading.get_text(" ", strip=True).lower().rsplit(":", 1)[-1].strip()
            word_class = sections.get(label, "")
        if not re.fullmatch(r"tr\d+", entry.get("id", "")):
            continue
        cells = entry.find_all("td", class_="td7nl", recursive=False)
        if len(cells) != 2:
            continue
        # Numeric vote counts are floated inside the translation cell.
        for cell in cells:
            for badge in cell.find_all("div", recursive=False):
                if badge.get_text(strip=True).isdigit():
                    badge.decompose()
        pos = word_class
        for cell in cells:
            for label in cell.find_all("var"):
                if label.get_text(strip=True) in {"{adj}", "{adv}"}:
                    pos = {"{adj}": "adjective", "{adv}": "adverb"}[
                        label.get_text(strip=True)
                    ]
        first, german = (" ".join(cell.stripped_strings) for cell in cells)
        source, target = (german, first) if source_lang == "de" else (first, german)
        row = (source, target, pos)
        if source and target and row not in seen:
            seen.add(row)
            rows.append(row)
    if rows:
        return rows
    if content.find("tr", id=re.compile(r"^tr\d+$")) is None and (
        "No entries found!" in text or "Leider keine Übersetzungen gefunden!" in text
    ):
        return []
    raise TranslateError("dict.cc returned an unrecognized results format")


def clean_text(value):
    soup = BeautifulSoup(str(value), "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    return " ".join(soup.get_text(" ").split())


def lookup(word, source_lang, language=DEFAULT_LANGUAGE, verbose=False):
    return parse_dictcc_response(
        fetch_dictcc(word, language=language, verbose=verbose),
        source_lang=source_lang,
    )


def parse_direction_and_words(terms):
    if terms[0] in DIRECTIONS:
        return terms[0], terms[1:]
    return "ten", terms


def build_parser():
    parser = ArgumentParser(description="Look up translations with dict.cc")
    parser.add_argument(
        "terms",
        nargs="*",
        help="optional direction (ten/fen, tfr/ffr, tit/fit) and words",
    )
    parser.add_argument(
        "-l", "--labels", action="store_true", help="show part of speech"
    )
    parser.add_argument("--loop", action="store_true", help="keep prompting for words")
    parser.add_argument("-m", "--max-entries", type=int)
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser


def print_table(rows, headers, crop=False):
    output = tabulate(rows, headers=headers)
    if crop:
        output = crop_to_columns(output)
    print(output)


def crop_to_columns(text):
    try:
        columns = int(os.environ.get("COLUMNS", ""))
    except ValueError:
        return text
    if columns < 2:
        return text
    return "\n".join(crop_line(line, columns) for line in text.splitlines())


def crop_line(line, columns):
    if len(line) <= columns:
        return line
    return line[: columns - 1] + "…"


def run_for_word(
    word, language, source_lang, headers, max_entries, show_labels, verbose
):
    try:
        translations = lookup(
            word,
            source_lang=source_lang,
            language=language,
            verbose=verbose,
        )[:max_entries]
    except TranslateError as error:
        print(f"{word}: {error}", file=sys.stderr)
        return 1

    if not translations:
        print(f"No translations found for {word!r} on dict.cc.")
        return 0

    if show_labels:
        print_table(translations, headers=headers + ["POS"])
    else:
        print_table([row[:2] for row in translations], headers=headers, crop=True)
    return 0


def run_loop(language, source_lang, headers, max_entries, show_labels, verbose):
    exit_code = 0
    while True:
        try:
            print(">", flush=True)
            word = input().strip()
        except EOFError:
            print()
            break
        except KeyboardInterrupt:
            print()
            return 130
        if not word:
            continue
        if exit_code:
            print()
        exit_code = max(
            exit_code,
            run_for_word(
                word, language, source_lang, headers, max_entries, show_labels, verbose
            ),
        )
    return exit_code


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.max_entries is not None and args.max_entries < 1:
        build_parser().error("--max-entries must be at least 1")
    if not args.loop and not args.terms:
        build_parser().error(
            "the following arguments are required: terms (or use --loop)"
        )

    try:
        direction, words = parse_direction_and_words(args.terms or ["ten"])
    except TranslateError as error:
        print(error, file=sys.stderr)
        raise SystemExit(2)
    if not args.loop and not words:
        print(f"{direction} requires at least one word", file=sys.stderr)
        raise SystemExit(2)

    language, source_lang, headers = DIRECTIONS[direction]
    max_entries = args.max_entries
    if max_entries is None:
        max_entries = 999 if args.labels else COMPACT_MAX_ENTRIES

    if args.loop:
        raise SystemExit(
            run_loop(
                language,
                source_lang,
                headers,
                max_entries,
                args.labels,
                args.verbose,
            )
        )

    exit_code = 0
    for index, word in enumerate(words):
        if index:
            print()
        exit_code = max(
            exit_code,
            run_for_word(
                word,
                language,
                source_lang,
                headers,
                max_entries,
                args.labels,
                args.verbose,
            ),
        )
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
