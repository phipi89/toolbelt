import os
import sys
from argparse import ArgumentParser

import requests
from bs4 import BeautifulSoup
from tabulate import tabulate


PONS_URL = "https://api.pons.com/v1/dictionary"
DEFAULT_LANGUAGE = "deen"
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


def fetch_pons(word, language=DEFAULT_LANGUAGE, verbose=False):
    api_key = os.environ.get("PONS_API_KEY")
    if not api_key:
        raise TranslateError("PONS_API_KEY is not set")

    params = {"q": word, "l": language}
    if verbose:
        print(f"Requesting {PONS_URL} q={word!r} l={language!r}", file=sys.stderr)

    response = requests.get(
        PONS_URL,
        params=params,
        headers={"X-Secret": api_key},
        timeout=15,
    )
    if response.status_code == 403:
        raise TranslateError("PONS rejected the API key")
    if not response.ok:
        raise TranslateError(f"PONS returned HTTP {response.status_code}")
    return response.json()


def parse_pons_response(data, source_lang=None):
    rows = []
    seen = set()

    for result in data or []:
        if source_lang and result.get("lang") != source_lang:
            continue
        for hit in result.get("hits", []):
            for rom in hit.get("roms", []):
                source_headword = clean_text(
                    rom.get("headword", "") or hit.get("headword", "")
                )
                word_class = clean_text(rom.get("wordclass", ""))
                for arab in rom.get("arabs", []):
                    for translation in arab.get("translations", []):
                        source = clean_text(translation.get("source", ""))
                        target = clean_text(translation.get("target", ""))
                        if not source:
                            source = source_headword
                        if not source or not target:
                            continue

                        row = (source, target, word_class)
                        if row in seen:
                            continue
                        seen.add(row)
                        rows.append(row)

    return rows


def clean_text(value):
    soup = BeautifulSoup(str(value), "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    return " ".join(soup.get_text(" ").split())


def lookup(word, source_lang, language=DEFAULT_LANGUAGE, verbose=False):
    return parse_pons_response(
        fetch_pons(word, language=language, verbose=verbose),
        source_lang=source_lang,
    )


def parse_direction_and_words(terms):
    if terms[0] in DIRECTIONS:
        return terms[0], terms[1:]
    return "ten", terms


def build_parser():
    parser = ArgumentParser(description="Look up translations with the PONS API")
    parser.add_argument(
        "terms",
        nargs="*",
        help="optional direction (ten/fen, tfr/ffr, tit/fit) and words",
    )
    parser.add_argument("-l", "--labels", action="store_true", help="show part of speech")
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


def run_for_word(word, language, source_lang, headers, max_entries, show_labels, verbose):
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
        print("\tNo translations found")
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
            run_for_word(word, language, source_lang, headers, max_entries, show_labels, verbose),
        )
    return exit_code


def main(argv=None):
    args = build_parser().parse_args(argv)
    if not args.loop and not args.terms:
        build_parser().error("the following arguments are required: terms (or use --loop)")

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
