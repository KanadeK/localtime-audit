"""Bounded streaming input and complete, non-overwriting report publication."""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import tempfile
from pathlib import Path

from . import __version__
from .core import load_zone
from .csvio import audit_csv

MAX_BYTES = 64 * 1024 * 1024
DELIMITERS = {"comma": ",", "tab": "\t", "semicolon": ";"}


class LimitedReader(io.RawIOBase):
    def __init__(self, stream, limit: int):
        self.stream = stream
        self.remaining = limit

    def readable(self) -> bool:
        return True

    def readinto(self, buffer) -> int:
        data = self.stream.read(min(len(buffer), self.remaining + 1))
        if len(data) > self.remaining:
            raise ValueError("input exceeds 64 MiB")
        buffer[: len(data)] = data
        self.remaining -= len(data)
        return len(data)


def positive(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be positive")
    return number


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit CSV wall-clock timestamps without silently selecting or shifting times."
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("--column", required=True, help="Local timestamp column")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--zone", help="One IANA zone for the entire file")
    group.add_argument("--zone-column", help="Column containing a zone for each record")
    parser.add_argument(
        "--output", required=True, type=Path, help="New CSV report; never overwritten"
    )
    parser.add_argument("--encoding", default="utf-8-sig")
    parser.add_argument("--delimiter", choices=list(DELIMITERS), default="comma")
    parser.add_argument("--max-rows", type=positive, default=1_000_000)
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Format of the stdout summary; the report is always CSV",
    )
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args(argv)
    temporary = None
    try:
        if os.path.lexists(args.output):
            raise FileExistsError("output already exists; choose a new name")
        if not args.input.is_file():
            raise ValueError("input must be an existing regular file")
        if args.zone is not None:
            load_zone(args.zone)
        # Same-directory staging keeps final publication on one filesystem.
        fd, temporary = tempfile.mkstemp(
            prefix=".localtime-audit-", suffix=".tmp", dir=args.output.parent
        )
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as output:
            with args.input.open("rb") as binary:
                with io.TextIOWrapper(
                    io.BufferedReader(LimitedReader(binary, MAX_BYTES)),
                    encoding=args.encoding,
                    newline="",
                ) as source:
                    summary = audit_csv(
                        source,
                        output,
                        args.column,
                        zone=args.zone,
                        zone_column=args.zone_column,
                        delimiter=DELIMITERS[args.delimiter],
                        max_rows=args.max_rows,
                    )
            output.flush()
            os.fsync(output.fileno())
        # Hard-link publication is atomic and fails if any destination already exists.
        os.link(temporary, args.output)
        if args.format == "json":
            print(json.dumps(summary, ensure_ascii=True, indent=2))
        else:
            print(
                f"{summary['total']} records: {summary['unique']} unique, {summary['ambiguous']} ambiguous, {summary['nonexistent']} nonexistent, {summary['invalid']} invalid; IANA {summary['iana']} (tzdata {summary['tzdata']})"
            )
        return int(bool(summary["ambiguous"] or summary["nonexistent"] or summary["invalid"]))
    except (OSError, UnicodeError, LookupError, ValueError) as exc:
        print(f"localtime-audit: {ascii(str(exc))}", file=sys.stderr)
        return 2
    finally:
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)
