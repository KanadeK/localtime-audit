"""Streaming strict CSV transformation that preserves original field values."""

from __future__ import annotations

import csv
from typing import TextIO

from .core import classify, data_version

AUDIT_COLUMNS = (
    "audit_record",
    "audit_line",
    "audit_status",
    "audit_reason",
    "audit_zone",
    "audit_utc_first",
    "audit_utc_second",
    "audit_offset_first",
    "audit_offset_second",
    "audit_tzdata",
    "audit_iana",
)


def audit_csv(
    source: TextIO,
    output: TextIO,
    column: str,
    *,
    zone: str | None = None,
    zone_column: str | None = None,
    delimiter: str = ",",
    max_rows: int = 1_000_000,
) -> dict:
    if (zone is None) == (zone_column is None):
        raise ValueError("choose exactly one of zone or zone_column")
    if max_rows < 1:
        raise ValueError("max_rows must be positive")
    reader = csv.reader(source, delimiter=delimiter, strict=True)
    writer = csv.writer(output, delimiter=delimiter, lineterminator="\n")
    versions = data_version()
    summary = {
        "schema_version": 1,
        "total": 0,
        "unique": 0,
        "ambiguous": 0,
        "nonexistent": 0,
        "invalid": 0,
        **versions,
    }
    try:
        headers = next(reader, None)
        if (
            not headers
            or any(not h or h != h.strip() or "\x00" in h for h in headers)
            or len(set(headers)) != len(headers)
        ):
            raise ValueError("CSV needs nonempty, unique headers without edge whitespace or NUL")
        if any(header in AUDIT_COLUMNS for header in headers):
            raise ValueError("CSV already contains reserved audit output columns")
        if column not in headers or (zone_column is not None and zone_column not in headers):
            raise ValueError("timestamp or zone column is missing from the header")
        timestamp_index = headers.index(column)
        zone_index = headers.index(zone_column) if zone_column is not None else None
        writer.writerow([*headers, *AUDIT_COLUMNS])
        previous_line = reader.line_num
        for row in reader:
            line = previous_line + 1
            previous_line = reader.line_num
            if not row:
                continue
            if len(row) != len(headers):
                raise ValueError(f"line {line}: expected {len(headers)} fields, got {len(row)}")
            if any("\x00" in value for value in row):
                raise ValueError(f"line {line}: NUL in CSV input")
            if summary["total"] >= max_rows:
                raise ValueError(f"row limit exceeded ({max_rows})")
            zone_key = zone if zone_index is None else row[zone_index]
            result = classify(row[timestamp_index], zone_key)
            summary["total"] += 1
            summary[result.status] += 1
            first = result.candidates[0] if result.candidates else None
            second = result.candidates[1] if len(result.candidates) == 2 else None
            writer.writerow(
                [
                    *row,
                    summary["total"],
                    line,
                    result.status,
                    result.reason,
                    zone_key,
                    first.utc_text() if first else "",
                    second.utc_text() if second else "",
                    first.offset_text() if first else "",
                    second.offset_text() if second else "",
                    versions["tzdata"],
                    versions["iana"],
                ]
            )
        return summary
    except csv.Error as exc:
        raise ValueError(f"CSV error near line {reader.line_num}: {exc}") from exc
