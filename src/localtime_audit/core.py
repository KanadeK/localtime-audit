"""Classify wall-clock timestamps by UTC roundtrip, without choosing a fold."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from importlib.resources import files
from zoneinfo import ZoneInfo

import tzdata

LOCAL_FORMAT = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}[ T][0-9]{2}:[0-9]{2}(?::[0-9]{2}(?:\.[0-9]{1,6})?)?"
)
ZONE_FORMAT = re.compile(r"[A-Za-z0-9._+-]+(?:/[A-Za-z0-9._+-]+)*")


@lru_cache(maxsize=256)
def load_zone(key: str) -> ZoneInfo:
    """Always read the installed tzdata package, never host-specific zone files."""
    if not ZONE_FORMAT.fullmatch(key) or any(part in {".", ".."} for part in key.split("/")):
        raise ValueError("invalid_zone")
    resource = files("tzdata.zoneinfo")
    for part in key.split("/"):
        resource = resource.joinpath(part)
    try:
        with resource.open("rb") as stream:
            return ZoneInfo.from_file(stream, key=key)
    except (OSError, ValueError) as exc:
        raise ValueError("unknown_zone") from exc


@dataclass(frozen=True)
class Candidate:
    utc: datetime
    offset_seconds: int

    def utc_text(self) -> str:
        return self.utc.isoformat().replace("+00:00", "Z")

    def offset_text(self) -> str:
        seconds = abs(self.offset_seconds)
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        text = f"{'-' if self.offset_seconds < 0 else '+'}{hours:02d}:{minutes:02d}"
        return text + (f":{seconds:02d}" if seconds else "")


@dataclass(frozen=True)
class Classification:
    status: str
    reason: str = ""
    candidates: tuple[Candidate, ...] = ()


def classify(value: str, zone_key: str) -> Classification:
    if not value:
        return Classification("invalid", "empty_datetime")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
    except ValueError:
        return Classification("invalid", "invalid_datetime")
    if parsed.tzinfo is not None:
        return Classification("invalid", "aware_input")
    if LOCAL_FORMAT.fullmatch(value) is None:
        return Classification("invalid", "invalid_datetime")
    if not zone_key:
        return Classification("invalid", "empty_zone")
    try:
        zone = load_zone(zone_key)
    except ValueError as exc:
        return Classification("invalid", str(exc))
    candidates = {}
    try:
        for fold in (0, 1):
            local = parsed.replace(tzinfo=zone, fold=fold)
            utc = local.astimezone(timezone.utc)
            roundtrip = utc.astimezone(zone).replace(tzinfo=None)
            if roundtrip == parsed:
                candidates[utc] = Candidate(utc, int(local.utcoffset().total_seconds()))
    except (OverflowError, ValueError):
        return Classification("invalid", "out_of_range")
    ordered = tuple(candidates[key] for key in sorted(candidates))
    if not ordered:
        return Classification("nonexistent", "clock_gap")
    if len(ordered) == 2:
        return Classification("ambiguous", "clock_fold", ordered)
    return Classification("unique", candidates=ordered)


def data_version() -> dict[str, str]:
    return {"tzdata": tzdata.__version__, "iana": tzdata.IANA_VERSION}
