import contextlib
import csv
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from localtime_audit.cli import main


class CLITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.input = self.root / "input.csv"
        self.output = self.root / "audit.csv"
        self.input.write_text(
            "time,zone\n2024-11-03T01:30:00,America/New_York\n2024-03-10T02:30:00,America/New_York\n",
            encoding="utf-8",
        )

    def invoke(self, *args, zone_column=True):
        stdout, stderr = io.StringIO(), io.StringIO()
        command = [str(self.input), "--column", "time", "--output", str(self.output)]
        if zone_column:
            command.extend(["--zone-column", "zone"])
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main([*command, *map(str, args)])
        return code, stdout.getvalue(), stderr.getvalue()

    def test_issues_return_one_with_a_complete_report(self):
        before = self.input.read_bytes()
        code, text, error = self.invoke("--format", "json")
        self.assertEqual((code, error), (1, ""))
        self.assertEqual(json.loads(text)["total"], 2)
        with self.output.open(encoding="utf-8", newline="") as stream:
            self.assertEqual(
                [row["audit_status"] for row in csv.DictReader(stream)],
                ["ambiguous", "nonexistent"],
            )
        self.assertEqual(self.input.read_bytes(), before)
        self.assertEqual(list(self.root.glob(".localtime-audit-*.tmp")), [])

    def test_unique_constant_zone_and_text_summary(self):
        self.input.write_text("time\n2024-01-01T08:00:00\n")
        code, text, error = self.invoke("--zone", "Asia/Shanghai", zone_column=False)
        self.assertEqual((code, error), (0, ""))
        self.assertIn("1 unique", text)
        self.assertIn("2024-01-01T00:00:00Z", self.output.read_text())

    def test_existing_output_and_input_are_protected(self):
        self.output.write_text("keep")
        self.assertEqual(self.invoke()[0], 2)
        self.assertEqual(self.output.read_text(), "keep")
        before = self.input.read_bytes()
        self.output = self.input
        self.assertEqual(self.invoke()[0], 2)
        self.assertEqual(self.input.read_bytes(), before)

    def test_late_parse_failure_cleans_staging_and_publishes_nothing(self):
        self.input.write_text('time,zone\n2024-01-01T00:00:00,UTC\n"unterminated')
        self.assertEqual(self.invoke()[0], 2)
        self.assertFalse(self.output.exists())
        self.assertEqual(list(self.root.glob(".localtime-audit-*.tmp")), [])

    def test_exclusive_publication_preserves_a_concurrent_writer(self):
        def concurrent_writer(source, destination):
            Path(destination).write_text("other writer")
            raise FileExistsError("destination appeared")

        with patch("localtime_audit.cli.os.link", side_effect=concurrent_writer):
            self.assertEqual(self.invoke()[0], 2)
        self.assertEqual(self.output.read_text(), "other writer")
        self.assertEqual(list(self.root.glob(".localtime-audit-*.tmp")), [])

    def test_unsupported_output_filesystem_fails_cleanly(self):
        with patch("localtime_audit.cli.os.link", side_effect=OSError("hard links unsupported")):
            self.assertEqual(self.invoke()[0], 2)
        self.assertFalse(self.output.exists())

    def test_byte_limit_encoding_and_missing_input(self):
        with patch("localtime_audit.cli.MAX_BYTES", 4):
            self.assertEqual(self.invoke()[0], 2)
        self.input.write_bytes(b"\xff")
        self.assertEqual(self.invoke()[0], 2)
        self.assertEqual(self.invoke("--encoding", "not-a-codec")[0], 2)
        self.input.unlink()
        self.assertEqual(self.invoke()[0], 2)
        self.assertFalse(self.output.exists())

    def test_global_unknown_zone_and_missing_output_parent(self):
        self.assertEqual(self.invoke("--zone", "Bogus/Zone", zone_column=False)[0], 2)
        self.output = self.root / "missing" / "report.csv"
        self.assertEqual(self.invoke()[0], 2)

    def test_row_limit_and_parser_validation(self):
        self.assertEqual(self.invoke("--max-rows", "1")[0], 2)
        with self.assertRaises(SystemExit) as caught:
            self.invoke("--max-rows", "0")
        self.assertEqual(caught.exception.code, 2)

    def test_bom_tsv_and_explicit_legacy_codec(self):
        for encoding in ("cp1252", "utf-8-sig"):
            with self.subTest(encoding=encoding):
                self.input.write_bytes(
                    "time\tzone\tnote\n2024-01-01T00:00:00\tUTC\tcafé\n".encode(encoding)
                )
                self.assertEqual(self.invoke("--delimiter", "tab", "--encoding", encoding)[0], 0)
                self.assertIn("café", self.output.read_text(encoding="utf-8"))
                self.output.unlink()

    def test_exact_byte_limit_accepts_eof_without_extra_byte(self):
        with patch("localtime_audit.cli.MAX_BYTES", len(self.input.read_bytes())):
            self.assertEqual(self.invoke()[0], 1)
        self.assertTrue(self.output.exists())

    def test_installed_module_end_to_end(self):
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "localtime_audit",
                str(self.input),
                "--column",
                "time",
                "--zone-column",
                "zone",
                "--output",
                str(self.output),
                "--format",
                "json",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["ambiguous"], 1)
        self.assertTrue(self.output.exists())

    def test_version(self):
        with (
            contextlib.redirect_stdout(io.StringIO()) as stdout,
            self.assertRaises(SystemExit) as caught,
        ):
            main(["--version"])
        self.assertEqual((caught.exception.code, stdout.getvalue().strip()), (0, "0.1.0"))
