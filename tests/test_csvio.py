import csv
import io
import unittest

from localtime_audit.csvio import audit_csv


class CSVTests(unittest.TestCase):
    def audit(self, text, **kwargs):
        output = io.StringIO(newline="")
        options = {"zone_column": "zone", **kwargs}
        summary = audit_csv(io.StringIO(text, newline=""), output, "time", **options)
        rows = list(
            csv.DictReader(io.StringIO(output.getvalue()), delimiter=options.get("delimiter", ","))
        )
        return summary, rows

    def test_complete_mixed_zone_flow_preserves_source_values(self):
        summary, rows = self.audit(
            'id,time,zone,note\n1,2024-11-03 01:30:00,America/New_York,"keep, exact"\n2,2024-03-10 02:30:00,America/New_York,note\n3,2024-01-01 05:45,Asia/Kathmandu,=source-text\n4,bad,UTC,invalid\n'
        )
        self.assertEqual(
            [summary[key] for key in ("total", "unique", "ambiguous", "nonexistent", "invalid")],
            [4, 1, 1, 1, 1],
        )
        self.assertEqual(rows[0]["note"], "keep, exact")
        self.assertEqual(rows[2]["note"], "=source-text")
        self.assertEqual(rows[0]["audit_utc_second"], "2024-11-03T06:30:00Z")
        self.assertEqual(rows[1]["audit_utc_first"], "")
        self.assertEqual(rows[2]["audit_utc_first"], "2024-01-01T00:00:00Z")
        self.assertEqual(rows[3]["audit_reason"], "invalid_datetime")

    def test_constant_zone_and_header_only(self):
        summary, rows = self.audit(
            "time\n2024-01-01T08:00:00\n", zone="Asia/Shanghai", zone_column=None
        )
        self.assertEqual(summary["unique"], 1)
        self.assertEqual(rows[0]["audit_zone"], "Asia/Shanghai")
        summary, rows = self.audit("time,zone\n")
        self.assertEqual((summary["total"], rows), (0, []))

    def test_multiline_csv_and_blank_records_keep_physical_lines(self):
        _, rows = self.audit(
            'time,zone,note\n2024-01-01T00:00:00,UTC,"two\nlines"\n\n2024-01-02T00:00:00,UTC,next\n'
        )
        self.assertEqual([row["audit_line"] for row in rows], ["2", "5"])
        self.assertEqual([row["audit_record"] for row in rows], ["1", "2"])
        self.assertEqual(rows[0]["note"], "two\nlines")

    def test_duplicate_missing_reserved_and_empty_headers(self):
        for text in (
            "",
            "time,time,zone\n",
            "time,,zone\n",
            "time ,zone\n",
            "time,zone,audit_status\n",
            "other,zone\n",
            "time,other\n",
        ):
            with self.subTest(text=text), self.assertRaises(ValueError):
                self.audit(text)

    def test_ragged_malformed_and_nul_rows(self):
        for text in (
            "time,zone\n2024-01-01T00:00:00\n",
            'time,zone\n"unterminated',
            "time,zone\n2024-01-01T00:00:00,UT\x00C\n",
        ):
            with self.subTest(text=text), self.assertRaises(ValueError):
                self.audit(text)

    def test_zone_column_errors_are_row_diagnostics(self):
        summary, rows = self.audit(
            "time,zone\n2024-01-01T00:00:00,Bogus/Zone\n2024-01-01T00:00:00,\n"
        )
        self.assertEqual(summary["invalid"], 2)
        self.assertEqual([row["audit_reason"] for row in rows], ["unknown_zone", "empty_zone"])

    def test_tsv(self):
        summary, rows = self.audit("time\tzone\n2024-01-01T00:00:00\tUTC\n", delimiter="\t")
        self.assertEqual(summary["unique"], 1)
        self.assertEqual(rows[0]["audit_offset_first"], "+00:00")

    def test_configuration_and_row_limit(self):
        with self.assertRaises(ValueError):
            self.audit("time,zone\n", zone="UTC")
        with self.assertRaises(ValueError):
            self.audit("time,zone\n", zone_column=None)
        with self.assertRaises(ValueError):
            self.audit("time,zone\n", max_rows=0)
        with self.assertRaisesRegex(ValueError, "row limit"):
            self.audit("time,zone\n2024-01-01T00:00:00,UTC\n2024-01-02T00:00:00,UTC", max_rows=1)
