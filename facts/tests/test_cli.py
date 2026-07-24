from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from facts import cli

GENERATED = {
    "title": "Tiny hearing movements",
    "fact": "Stereocilia can move by less than one nanometre near hearing threshold.",
    "context": "The estimate depends on cochlear amplification.",
    "tags": ["Hearing", "Biophysics", "hearing"],
}


class FactsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = Path(self.temp_dir.name) / "facts.json"
        self.env = patch.dict(os.environ, {"FACTS_PATH": str(self.path)})
        self.env.start()

    def tearDown(self) -> None:
        self.env.stop()
        self.temp_dir.cleanup()

    def test_extracts_plain_or_fenced_json(self) -> None:
        self.assertEqual(cli._extract_json(json.dumps(GENERATED)), GENERATED)
        self.assertEqual(
            cli._extract_json(f"```json\n{json.dumps(GENERATED)}\n```"),
            GENERATED,
        )
        with self.assertRaises(ValueError):
            cli._extract_json(f"Result:\n{json.dumps(GENERATED)}")
        with self.assertRaises(ValueError):
            cli._extract_json(f"{json.dumps(GENERATED)}\n{json.dumps(GENERATED)}")

    def test_record_preserves_raw_input_and_deduplicates_sources(self) -> None:
        raw = "  A fact\nhttps://example.com/source.\n"
        record = cli._record(
            raw,
            cli._normalize_generated(GENERATED),
            ["https://example.com/source"],
        )

        self.assertEqual(record["raw_input"], raw)
        self.assertEqual(record["tags"], ["hearing", "biophysics"])
        self.assertEqual(
            record["sources"], [{"reference": "https://example.com/source"}]
        )

    def test_slug_transliterates_math_symbols(self) -> None:
        self.assertEqual(cli._slug("π × 10^7 Sekunden"), "pi-x-10-7-sekunden")

    def test_explicit_source_is_preserved_verbatim(self) -> None:
        source = "https://en.wikipedia.org/wiki/Foo_(bar)"

        self.assertEqual(cli._sources("", [source]), [{"reference": source}])
        self.assertEqual(cli._sources(source, []), [{"reference": source}])

    def test_save_is_loadable(self) -> None:
        fact = cli._record("raw", cli._normalize_generated(GENERATED), [])
        data = {"schema_version": 1, "facts": [fact]}

        cli._save(data)

        self.assertEqual(cli._load(), data)

    def test_opencode_uses_fresh_pure_session(self) -> None:
        completed = subprocess.CompletedProcess(
            [], 0, stdout=json.dumps(GENERATED), stderr=""
        )
        with patch.object(cli.subprocess, "run", return_value=completed) as run:
            self.assertEqual(cli._enrich("raw"), cli._normalize_generated(GENERATED))

        command = run.call_args.args[0]
        self.assertEqual(command[:3], ["opencode", "run", "--pure"])
        self.assertIn("facts", command)
        self.assertNotIn("-c", command)
        self.assertNotIn("--continue", command)
        config = json.loads(run.call_args.kwargs["env"]["OPENCODE_CONFIG_CONTENT"])
        self.assertEqual(config["permission"], "deny")
        self.assertEqual(config["agent"]["facts"]["permission"], "deny")

    def test_prompt_examples_are_valid_and_exclude_program_owned_sources(self) -> None:
        examples = cli._prompt_examples()

        self.assertEqual(len(examples), 3)
        self.assertTrue(all("sources" not in example["output"] for example in examples))
        self.assertEqual(examples[0]["output"]["title"], "Empfindlichkeit des Gehörs")

    def test_prompt_places_actual_payload_after_examples(self) -> None:
        prompt = cli._prompt("A unique submitted fact")

        self.assertIn("Write the title, fact, context, and tags in German", prompt)
        self.assertEqual(prompt.count("A unique submitted fact"), 1)
        self.assertGreater(
            prompt.index("A unique submitted fact"),
            prompt.index("Empfindlichkeit des Gehörs"),
        )

    def test_add_writes_validated_fact(self) -> None:
        args = argparse.Namespace(
            text=["Raw", "fact"],
            source=["https://example.com"],
            yes=True,
        )
        with (
            patch.object(cli, "_enrich", return_value=GENERATED),
            redirect_stdout(io.StringIO()),
        ):
            cli._add(args)

        facts = cli._load()["facts"]
        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0]["raw_input"], "Raw fact")

    def test_declined_fact_is_not_saved(self) -> None:
        args = argparse.Namespace(text=["Raw fact"], source=[], yes=False)
        with (
            patch.object(cli, "_enrich", return_value=GENERATED),
            patch.object(cli, "_confirm", return_value=False),
            redirect_stdout(io.StringIO()),
        ):
            cli._add(args)

        self.assertFalse(self.path.exists())

    def test_default_and_random_show_a_fact(self) -> None:
        fact = cli._record("raw", cli._normalize_generated(GENERATED), [])
        cli._save({"schema_version": 1, "facts": [fact]})

        for argv in ([], ["random"]):
            output = io.StringIO()
            with redirect_stdout(output):
                cli.main(argv)
            self.assertEqual(output.getvalue(), f"{fact['fact']}\n")

    def test_random_n_prints_distinct_facts(self) -> None:
        facts = []
        for index in range(3):
            generated = cli._normalize_generated(
                {
                    **GENERATED,
                    "title": f"Title {index}",
                    "fact": f"Fact {index}",
                }
            )
            facts.append(cli._record(f"raw {index}", generated, []))
        cli._save({"schema_version": 1, "facts": facts})

        output = io.StringIO()
        with (
            patch.object(cli.random, "sample", return_value=[facts[0], facts[2]]),
            redirect_stdout(output),
        ):
            cli.main(["random", "-n", "2"])

        self.assertEqual(output.getvalue(), "Fact 0\n\nFact 2\n")

    def test_default_random_accepts_n(self) -> None:
        facts = [
            cli._record("raw", cli._normalize_generated(GENERATED), []),
        ]
        cli._save({"schema_version": 1, "facts": facts})

        output = io.StringIO()
        with redirect_stdout(output):
            cli.main(["-n", "1"])

        self.assertEqual(output.getvalue(), f"{facts[0]['fact']}\n")

    def test_random_rejects_more_than_available(self) -> None:
        fact = cli._record("raw", cli._normalize_generated(GENERATED), [])
        cli._save({"schema_version": 1, "facts": [fact]})

        with self.assertRaises(SystemExit):
            cli.main(["random", "-n", "2"])

    def test_duplicate_raw_input_is_rejected(self) -> None:
        args = argparse.Namespace(text=["same"], source=[], yes=True)
        with (
            patch.object(cli, "_enrich", return_value=GENERATED) as enrich,
            redirect_stdout(io.StringIO()),
        ):
            cli._add(args)
            with self.assertRaises(SystemExit):
                cli._add(args)

        enrich.assert_called_once_with("same")

    def test_concurrent_appends_do_not_lose_facts(self) -> None:
        generated = cli._normalize_generated(GENERATED)
        records = [cli._record(f"raw {index}", generated, []) for index in range(10)]

        with ThreadPoolExecutor(max_workers=5) as executor:
            list(executor.map(cli._append_fact, records))

        self.assertEqual(len(cli._load()["facts"]), 10)

    def test_list_and_show(self) -> None:
        fact = cli._record(
            "raw", cli._normalize_generated(GENERATED), ["https://example.com"]
        )
        cli._save({"schema_version": 1, "facts": [fact]})

        list_output = io.StringIO()
        with redirect_stdout(list_output):
            cli.main(["list"])

        show_output = io.StringIO()
        with redirect_stdout(show_output):
            cli.main(["show", fact["id"][:12]])

        self.assertEqual(list_output.getvalue(), f"{fact['title']}\n")
        self.assertEqual(show_output.getvalue(), f"{fact['fact']}\n")

    def test_show_long_includes_metadata(self) -> None:
        fact = cli._record(
            "raw", cli._normalize_generated(GENERATED), ["https://example.com"]
        )
        cli._save({"schema_version": 1, "facts": [fact]})

        output = io.StringIO()
        with redirect_stdout(output):
            cli.main(["show", fact["id"], "--long"])

        rendered = output.getvalue()
        self.assertIn(fact["title"], rendered)
        self.assertIn(fact["fact"], rendered)
        self.assertIn(fact["context"], rendered)
        self.assertIn("https://example.com", rendered)

    def test_rejects_non_object_database(self) -> None:
        self.path.write_text("[]", encoding="utf-8")

        with self.assertRaises(SystemExit):
            cli._load()


if __name__ == "__main__":
    unittest.main()
