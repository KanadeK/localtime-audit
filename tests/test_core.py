import random
import unittest
from datetime import datetime, timedelta, timezone

from localtime_audit.core import Candidate, classify, data_version, load_zone


class ClassificationTests(unittest.TestCase):
    def test_normal_timestamp_and_microseconds(self):
        result = classify("2024-01-15 10:00:00.123456", "America/New_York")
        self.assertEqual(result.status, "unique")
        self.assertEqual(result.candidates[0].utc_text(), "2024-01-15T15:00:00.123456Z")
        self.assertEqual(result.candidates[0].offset_text(), "-05:00")

    def test_fold_has_two_ordered_utc_candidates(self):
        result = classify("2024-11-03 01:30:00", "America/New_York")
        self.assertEqual((result.status, result.reason), ("ambiguous", "clock_fold"))
        self.assertEqual(
            [c.utc_text() for c in result.candidates],
            ["2024-11-03T05:30:00Z", "2024-11-03T06:30:00Z"],
        )
        self.assertEqual([c.offset_text() for c in result.candidates], ["-04:00", "-05:00"])

    def test_gap_has_no_candidate(self):
        result = classify("2024-03-10T02:30:00", "America/New_York")
        self.assertEqual(
            (result.status, result.reason, result.candidates), ("nonexistent", "clock_gap", ())
        )

    def test_half_hour_fold_and_gap(self):
        fold = classify("2024-04-07 01:45:00", "Australia/Lord_Howe")
        gap = classify("2024-10-06 02:15:00", "Australia/Lord_Howe")
        self.assertEqual(fold.status, "ambiguous")
        self.assertEqual(
            [c.utc_text() for c in fold.candidates],
            ["2024-04-06T14:45:00Z", "2024-04-06T15:15:00Z"],
        )
        self.assertEqual((fold.candidates[1].utc - fold.candidates[0].utc).total_seconds(), 1800)
        self.assertEqual(gap.status, "nonexistent")

    def test_whole_skipped_day(self):
        self.assertEqual(classify("2011-12-30T12:00:00", "Pacific/Apia").status, "nonexistent")

    def test_quarter_hour_zone_and_minute_precision(self):
        result = classify("2024-01-01 05:45", "Asia/Kathmandu")
        self.assertEqual(result.status, "unique")
        self.assertEqual(
            (result.candidates[0].utc_text(), result.candidates[0].offset_text()),
            ("2024-01-01T00:00:00Z", "+05:45"),
        )

    def test_fold_gap_boundaries_are_unique_outside_transition(self):
        for value in (
            "2024-03-10T01:59:59",
            "2024-03-10T03:00:00",
            "2024-11-03T00:59:59",
            "2024-11-03T02:00:00",
        ):
            with self.subTest(value=value):
                self.assertEqual(classify(value, "America/New_York").status, "unique")

    def test_aware_inputs_are_explicitly_rejected(self):
        for value in (
            "2024-01-01T00:00:00Z",
            "2024-01-01T00:00:00+08:00",
            "2024-01-01T00:00-04:00",
        ):
            with self.subTest(value=value):
                result = classify(value, "UTC")
                self.assertEqual((result.status, result.reason), ("invalid", "aware_input"))

    def test_strict_format_prevents_inference_or_precision_loss(self):
        for value in (
            "2024-01-01",
            "20240101T000000",
            "2024-W01-1T00:00:00",
            "2024-01-01T00:00:00.1234567",
            "2024-02-30T00:00:00",
            "2024-01-01T24:00:00",
            "2024-01-01T00:00:60",
            " 2024-01-01T00:00:00",
            "not-a-date",
        ):
            with self.subTest(value=value):
                result = classify(value, "UTC")
                self.assertEqual((result.status, result.reason), ("invalid", "invalid_datetime"))
        self.assertEqual(classify("", "UTC").reason, "empty_datetime")

    def test_invalid_or_unknown_zone(self):
        for zone in (
            "../UTC",
            "/etc/passwd",
            "America/../UTC",
            "Asia\\Shanghai",
            "UTC ",
            "Asia/No_Such_City",
            "America",
        ):
            with self.subTest(zone=zone):
                result = classify("2024-01-01T00:00:00", zone)
                self.assertEqual(result.status, "invalid")
                self.assertIn(result.reason, {"invalid_zone", "unknown_zone"})
        self.assertEqual(classify("2024-01-01T00:00:00", "").reason, "empty_zone")

    def test_extreme_dates_do_not_overflow_the_process(self):
        self.assertEqual(classify("0001-01-01T00:00:00", "Asia/Shanghai").reason, "out_of_range")
        self.assertEqual(classify("0001-01-01T00:00:00", "UTC").status, "unique")
        self.assertEqual(classify("9999-12-31T23:59:59", "America/New_York").reason, "out_of_range")

    def test_historical_offset_seconds_are_rendered(self):
        self.assertEqual(
            Candidate(datetime(1900, 1, 1, tzinfo=timezone.utc), -1521).offset_text(), "-00:25:21"
        )
        self.assertEqual(
            Candidate(datetime(1900, 1, 1, tzinfo=timezone.utc), 561).offset_text(), "+00:09:21"
        )

    def test_version_and_cache_are_bounded(self):
        self.assertTrue(data_version()["tzdata"])
        self.assertTrue(data_version()["iana"])
        self.assertEqual(load_zone.cache_info().maxsize, 256)
        self.assertEqual(load_zone("Etc/UTC").key, "Etc/UTC")

    def test_real_utc_instants_are_never_lost_in_classification(self):
        rng = random.Random(495)  # noqa: S311 -- reproducible timestamp fixtures
        base = datetime(2010, 1, 1, tzinfo=timezone.utc)
        for zone_key in (
            "America/New_York",
            "Australia/Lord_Howe",
            "Pacific/Apia",
            "Europe/Dublin",
            "Asia/Kathmandu",
        ):
            zone = load_zone(zone_key)
            for _ in range(100):
                original = base + timedelta(minutes=rng.randrange(15 * 366 * 24 * 60))
                local = original.astimezone(zone).replace(tzinfo=None)
                result = classify(local.isoformat(), zone_key)
                self.assertIn(original, [c.utc for c in result.candidates])
                for candidate in result.candidates:
                    self.assertEqual(candidate.utc.astimezone(zone).replace(tzinfo=None), local)
