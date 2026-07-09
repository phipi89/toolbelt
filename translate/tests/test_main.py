import os
import unittest
from io import StringIO
from unittest.mock import Mock, patch

from translate.main import (
    TranslateError,
    clean_text,
    crop_to_columns,
    fetch_pons,
    main,
    parse_direction_and_words,
    parse_pons_response,
)


class PonsTest(unittest.TestCase):
    def test_parse_pons_response_extracts_translations(self):
        data = [
            {
                "lang": "de",
                "hits": [
                    {
                        "roms": [
                            {
                                "headword": "fantastisch",
                                "wordclass": "ADJ",
                                "arabs": [
                                    {
                                        "translations": [
                                            {
                                                "source": "<strong>fantastisch</strong>",
                                                "target": "fantastic",
                                            },
                                            {
                                                "source": "fantastisch",
                                                "target": "terrific",
                                            },
                                        ]
                                    }
                                ],
                            }
                        ],
                    }
                ]
            }
        ]

        self.assertEqual(
            parse_pons_response(data),
            [
                ("fantastisch", "fantastic", "ADJ"),
                ("fantastisch", "terrific", "ADJ"),
            ],
        )

    def test_parse_pons_response_uses_headword_when_source_is_missing(self):
        data = [
            {
                "lang": "en",
                "hits": [
                    {
                        "roms": [
                            {
                                "headword": "house",
                                "arabs": [
                                    {"translations": [{"target": "das Haus"}]},
                                ]
                            }
                        ],
                    }
                ]
            }
        ]

        self.assertEqual(parse_pons_response(data), [("house", "das Haus", "")])

    def test_parse_pons_response_deduplicates_rows(self):
        data = [
            {
                "lang": "en",
                "hits": [
                    {
                        "roms": [
                            {
                                "headword": "house",
                                "wordclass": "N",
                                "arabs": [
                                    {
                                        "translations": [
                                            {"source": "house", "target": "Haus"},
                                            {"source": "house", "target": "Haus"},
                                        ]
                                    }
                                ],
                            }
                        ],
                    }
                ]
            }
        ]

        self.assertEqual(parse_pons_response(data), [("house", "Haus", "N")])

    def test_parse_pons_response_filters_source_language(self):
        data = [
            {
                "lang": "en",
                "hits": [
                    {
                        "roms": [
                            {
                                "headword": "house",
                                "arabs": [
                                    {"translations": [{"target": "Haus"}]},
                                ],
                            }
                        ],
                    }
                ],
            },
            {
                "lang": "de",
                "hits": [
                    {
                        "roms": [
                            {
                                "headword": "House",
                                "arabs": [
                                    {"translations": [{"target": "house music"}]},
                                ],
                            }
                        ],
                    }
                ],
            },
        ]

        self.assertEqual(parse_pons_response(data, source_lang="en"), [("house", "Haus", "")])

    def test_clean_text_strips_html_and_whitespace(self):
        self.assertEqual(clean_text("<b>das</b> &nbsp; Haus"), "das Haus")

    def test_fetch_pons_requires_api_key(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(TranslateError, "PONS_API_KEY"):
                fetch_pons("house")

    def test_fetch_pons_sends_api_key_header(self):
        response = Mock(ok=True, status_code=200)
        response.json.return_value = []

        with patch.dict(os.environ, {"PONS_API_KEY": "secret"}, clear=True):
            with patch("translate.main.requests.get", return_value=response) as get:
                self.assertEqual(fetch_pons("house"), [])

        get.assert_called_once()
        self.assertEqual(get.call_args.kwargs["headers"], {"X-Secret": "secret"})
        self.assertEqual(get.call_args.kwargs["params"], {"q": "house", "l": "deen"})

    def test_parse_direction_defaults_to_german_to_english(self):
        self.assertEqual(parse_direction_and_words(["fantastisch"]), ("ten", ["fantastisch"]))

    def test_parse_direction_accepts_fen(self):
        self.assertEqual(parse_direction_and_words(["fen", "house"]), ("fen", ["house"]))

    def test_parse_direction_accepts_french_and_italian(self):
        self.assertEqual(parse_direction_and_words(["tfr", "Haus"]), ("tfr", ["Haus"]))
        self.assertEqual(parse_direction_and_words(["ffr", "maison"]), ("ffr", ["maison"]))
        self.assertEqual(parse_direction_and_words(["tit", "Haus"]), ("tit", ["Haus"]))
        self.assertEqual(parse_direction_and_words(["fit", "casa"]), ("fit", ["casa"]))

    def test_main_hides_pos_by_default(self):
        with patch("translate.main.lookup", return_value=[("house", "Haus", "noun")]):
            with patch("sys.stdout", new_callable=StringIO) as stdout:
                with self.assertRaises(SystemExit) as raised:
                    main(["fen", "house"])

        self.assertEqual(raised.exception.code, 0)
        output = stdout.getvalue()
        self.assertIn("English", output)
        self.assertIn("German", output)
        self.assertNotIn("POS", output)
        self.assertNotIn("noun", output)

    def test_main_limits_compact_output_to_six_rows_by_default(self):
        rows = [(f"source {index}", f"target {index}", "noun") for index in range(8)]

        with patch("translate.main.lookup", return_value=rows):
            with patch("sys.stdout", new_callable=StringIO) as stdout:
                with self.assertRaises(SystemExit) as raised:
                    main(["fen", "house"])

        self.assertEqual(raised.exception.code, 0)
        output = stdout.getvalue()
        self.assertIn("source 5", output)
        self.assertNotIn("source 6", output)

    def test_main_max_entries_overrides_compact_default(self):
        rows = [(f"source {index}", f"target {index}", "noun") for index in range(8)]

        with patch("translate.main.lookup", return_value=rows):
            with patch("sys.stdout", new_callable=StringIO) as stdout:
                with self.assertRaises(SystemExit) as raised:
                    main(["-m", "7", "fen", "house"])

        self.assertEqual(raised.exception.code, 0)
        output = stdout.getvalue()
        self.assertIn("source 6", output)
        self.assertNotIn("source 7", output)

    def test_main_shows_pos_with_labels_flag(self):
        with patch("translate.main.lookup", return_value=[("house", "Haus", "noun")]):
            with patch("sys.stdout", new_callable=StringIO) as stdout:
                with self.assertRaises(SystemExit) as raised:
                    main(["-l", "fen", "house"])

        self.assertEqual(raised.exception.code, 0)
        output = stdout.getvalue()
        self.assertIn("POS", output)
        self.assertIn("noun", output)

    def test_main_requires_terms_without_loop(self):
        with patch("sys.stderr", new_callable=StringIO):
            with self.assertRaises(SystemExit) as raised:
                main([])

        self.assertEqual(raised.exception.code, 2)

    def test_loop_reads_input_until_eof(self):
        inputs = iter(["house", "", "home"])

        def fake_input():
            try:
                return next(inputs)
            except StopIteration:
                raise EOFError

        with patch("translate.main.input", side_effect=fake_input):
            with patch("translate.main.lookup", return_value=[("house", "Haus", "noun")]) as lookup:
                with patch("sys.stdout", new_callable=StringIO) as stdout:
                    with self.assertRaises(SystemExit) as raised:
                        main(["--loop", "fen"])

        self.assertEqual(raised.exception.code, 0)
        self.assertEqual(lookup.call_count, 2)
        self.assertEqual(lookup.call_args_list[0].args[0], "house")
        self.assertEqual(lookup.call_args_list[0].kwargs["source_lang"], "en")
        self.assertEqual(lookup.call_args_list[1].args[0], "home")
        self.assertIn("English", stdout.getvalue())

    def test_loop_defaults_to_german_to_english(self):
        with patch("translate.main.input", side_effect=["fantastisch", EOFError]):
            with patch("translate.main.lookup", return_value=[("fantastisch", "fantastic", "adjective")]) as lookup:
                with patch("sys.stdout", new_callable=StringIO):
                    with self.assertRaises(SystemExit) as raised:
                        main(["--loop"])

        self.assertEqual(raised.exception.code, 0)
        self.assertEqual(lookup.call_args.kwargs["source_lang"], "de")

    def test_crop_to_columns_uses_ellipsis(self):
        with patch.dict(os.environ, {"COLUMNS": "10"}, clear=True):
            self.assertEqual(crop_to_columns("1234567890\n12345678901"), "1234567890\n123456789…")


if __name__ == "__main__":
    unittest.main()
