import os
import unittest
from io import StringIO
from unittest.mock import Mock, patch

import requests
from translate.main import (
    DIRECTIONS,
    USER_AGENT,
    TranslateError,
    crop_to_columns,
    fetch_dictcc,
    lookup,
    main,
    parse_dictcc_response,
    parse_direction_and_words,
)


def page(body):
    return (
        '<html><head><meta charset="utf-8"><title>dict.cc</title></head>'
        '<body><div id="maincontent"><input id="sinp">'
        f"<table>{body}</table></div></body></html>"
    )


def row(first, german, number=1):
    return (
        f'<tr id="tr{number}"><td class="td7cml"></td>'
        f'<td class="td7nl">{first}</td>'
        f'<td class="td7nl">{german}</td><td class="td7cmr"></td></tr>'
    )


class DictccTests(unittest.TestCase):
    def test_extracts_pairs_and_removes_vote_counts(self):
        html = page(row("to put into perspective", "<div>592</div><b>relativieren</b>"))
        self.assertEqual(
            parse_dictcc_response(html),
            [("relativieren", "to put into perspective", "")],
        )

    def test_reverses_columns_for_each_direction(self):
        examples = {
            "deen": ("house", "Haus"),
            "defr": ("maison", "Haus"),
            "deit": ("casa", "Haus"),
        }
        for direction, (language, source, _) in DIRECTIONS.items():
            first, german = examples[language]
            with self.subTest(direction=direction):
                expected = (german, first) if source == "de" else (first, german)
                self.assertEqual(
                    parse_dictcc_response(page(row(first, german)), source)[0][:2],
                    expected,
                )

    def test_preserves_annotations_and_detects_part_of_speech(self):
        html = page(
            '<tr><td colspan="4" class="td6">Verben</td></tr>'
            + row(
                "to qualify sth. <kbd>[statement etc.]</kbd>",
                "etw. <sup>Akk.</sup> relativieren",
            )
        )
        self.assertEqual(
            parse_dictcc_response(html),
            [("etw. Akk. relativieren", "to qualify sth. [statement etc.]", "verb")],
        )
        html = page(row('house <var title="adjective">{adj}</var>', "Haus-"))
        self.assertEqual(parse_dictcc_response(html)[0][2], "adjective")

    def test_deduplicates_without_losing_different_meanings(self):
        html = page(
            row("test", "Probe") + row("test", "Probe", 2) + row("test", "Prüfung", 3)
        )
        self.assertEqual(len(parse_dictcc_response(html)), 2)

    def test_explicit_no_results_returns_empty(self):
        html = page("No entries found! Leider keine Übersetzungen gefunden!")
        self.assertEqual(parse_dictcc_response(html), [])

    def test_challenge_phrase_in_translation_is_not_mistaken_for_a_block(self):
        html = page(row("just a moment", "einen Moment"))
        self.assertEqual(
            parse_dictcc_response(html), [("einen Moment", "just a moment", "")]
        )

    def test_block_pages_are_errors_even_with_http_200(self):
        for html in (
            "Please don't run crawlers against dict.cc and don't try to make the dictionary available offline.",
            "<html><title>Just a moment...</title></html>",
        ):
            with (
                self.subTest(html=html),
                self.assertRaisesRegex(TranslateError, "blocked"),
            ):
                parse_dictcc_response(html)

    def test_unrecognized_or_malformed_results_are_not_reported_as_no_results(self):
        for html in (
            "<html>Service unavailable</html>",
            page("<p>Layout changed</p>"),
            page('<tr id="tr1"><td>broken</td></tr>No entries found!'),
        ):
            with (
                self.subTest(html=html),
                self.assertRaisesRegex(TranslateError, "unrecognized"),
            ):
                parse_dictcc_response(html)

    def test_ignores_unrelated_links_and_scripts(self):
        html = page('<script>No entries found!</script><a href="/">house</a>')
        with self.assertRaises(TranslateError):
            parse_dictcc_response(html)

    def test_fetch_sends_query_and_identifies_client_without_api_key(self):
        response = Mock(
            ok=True, status_code=200, content=page(row("house", "Haus")).encode()
        )
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("translate.main.requests.get", return_value=response) as get,
        ):
            self.assertEqual(fetch_dictcc("relativieren"), response.content)
        self.assertEqual(get.call_args.kwargs["headers"], {"User-Agent": USER_AGENT})
        self.assertEqual(get.call_args.kwargs["params"], {"s": "relativieren"})
        self.assertEqual(get.call_args.kwargs["timeout"], 15)

    def test_fetch_uses_language_subdomain(self):
        with patch(
            "translate.main.requests.get", return_value=Mock(ok=True, content=b"")
        ) as get:
            fetch_dictcc("maison", language="defr")
            self.assertEqual(get.call_args.args[0], "https://defr.dict.cc/")
            fetch_dictcc("casa", language="deit")
            self.assertEqual(get.call_args.args[0], "https://deit.dict.cc/")

    def test_http_and_network_errors_are_reported(self):
        with (
            patch(
                "translate.main.requests.get",
                return_value=Mock(ok=False, status_code=429),
            ),
            self.assertRaisesRegex(TranslateError, "HTTP 429"),
        ):
            fetch_dictcc("house")
        with (
            patch(
                "translate.main.requests.get", side_effect=requests.Timeout("timed out")
            ),
            self.assertRaisesRegex(TranslateError, "request failed"),
        ):
            fetch_dictcc("house")

    def test_lookup_fetches_and_parses_in_requested_direction(self):
        with patch(
            "translate.main.fetch_dictcc", return_value=page(row("maison", "Haus"))
        ) as fetch:
            self.assertEqual(
                lookup("Haus", "de", language="defr"), [("Haus", "maison", "")]
            )
        fetch.assert_called_once_with("Haus", language="defr", verbose=False)


class CliTests(unittest.TestCase):
    def run_cli(self, arguments, results):
        with (
            patch("translate.main.lookup", return_value=results),
            patch("sys.stdout", new_callable=StringIO) as stdout,
            patch("sys.stderr", new_callable=StringIO) as stderr,
            self.assertRaises(SystemExit) as raised,
        ):
            main(arguments)
        return raised.exception.code, stdout.getvalue(), stderr.getvalue()

    def test_direction_shortcuts_and_default(self):
        self.assertEqual(parse_direction_and_words(["Haus"]), ("ten", ["Haus"]))
        for direction in DIRECTIONS:
            self.assertEqual(
                parse_direction_and_words([direction, "word"]), (direction, ["word"])
            )

    def test_hides_part_of_speech_by_default(self):
        code, output, _ = self.run_cli(["fen", "house"], [("house", "Haus", "noun")])
        self.assertEqual(code, 0)
        self.assertIn("English", output)
        self.assertIn("German", output)
        self.assertNotIn("POS", output)
        self.assertNotIn("noun", output)

    def test_labels_flag_displays_part_of_speech(self):
        code, output, _ = self.run_cli(
            ["-l", "fen", "house"], [("house", "Haus", "noun")]
        )
        self.assertEqual(code, 0)
        self.assertIn("POS", output)
        self.assertIn("noun", output)

    def test_compact_output_limits_to_six_and_max_entries_overrides(self):
        rows = [(f"source {index}", f"target {index}", "noun") for index in range(8)]
        _, output, _ = self.run_cli(["fen", "house"], rows)
        self.assertIn("source 5", output)
        self.assertNotIn("source 6", output)
        _, output, _ = self.run_cli(["-m", "7", "fen", "house"], rows)
        self.assertIn("source 6", output)
        self.assertNotIn("source 7", output)

    def test_no_results_includes_word_and_provider(self):
        code, output, error = self.run_cli(["ten", "unknownword"], [])
        self.assertEqual(code, 0)
        self.assertIn("No translations found for 'unknownword' on dict.cc.", output)
        self.assertEqual(error, "")

    def test_block_is_error_not_no_results(self):
        with (
            patch(
                "translate.main.lookup",
                side_effect=TranslateError("dict.cc blocked the request"),
            ),
            patch("sys.stdout", new_callable=StringIO) as stdout,
            patch("sys.stderr", new_callable=StringIO) as stderr,
            self.assertRaises(SystemExit) as raised,
        ):
            main(["fen", "house"])
        self.assertEqual(raised.exception.code, 1)
        self.assertIn("blocked", stderr.getvalue())
        self.assertNotIn("No translations", stdout.getvalue())

    def test_requires_words_and_positive_limit(self):
        for arguments in ([], ["fen"], ["-m", "0", "house"]):
            with self.subTest(arguments=arguments):
                code, _, _ = self.run_cli(arguments, [])
                self.assertEqual(code, 2)

    def test_loop_survives_missing_words_and_request_errors(self):
        with (
            patch(
                "translate.main.input",
                side_effect=["missing", "blocked", "house", EOFError],
            ),
            patch(
                "translate.main.lookup",
                side_effect=[
                    [],
                    TranslateError("blocked"),
                    [("house", "Haus", "noun")],
                ],
            ) as lookup_mock,
            patch("sys.stdout", new_callable=StringIO) as stdout,
            patch("sys.stderr", new_callable=StringIO),
            self.assertRaises(SystemExit) as raised,
        ):
            main(["--loop", "fen"])
        self.assertEqual(raised.exception.code, 1)
        self.assertEqual(lookup_mock.call_count, 3)
        self.assertEqual(lookup_mock.call_args.kwargs["source_lang"], "en")
        self.assertIn("No translations found", stdout.getvalue())
        self.assertIn("Haus", stdout.getvalue())

    def test_loop_defaults_to_german_to_english(self):
        with (
            patch("translate.main.input", side_effect=["Haus", EOFError]),
            patch(
                "translate.main.lookup", return_value=[("Haus", "house", "noun")]
            ) as lookup_mock,
            patch("sys.stdout", new_callable=StringIO),
            self.assertRaises(SystemExit),
        ):
            main(["--loop"])
        self.assertEqual(lookup_mock.call_args.kwargs["source_lang"], "de")

    def test_crop_to_columns_uses_ellipsis(self):
        with patch.dict(os.environ, {"COLUMNS": "10"}, clear=True):
            self.assertEqual(
                crop_to_columns("1234567890\n12345678901"), "1234567890\n123456789…"
            )
