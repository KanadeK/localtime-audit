# Release validation — 0.1.0

Local environment: Windows, Python 3.13.16, tzdata 2026.5 / IANA 2026e, checked 2026-10-24.

- 35 unittest cases, no platform skips. Known-answer fixtures cover New York folds/gaps, Lord Howe half-hour transitions, Samoa's skipped day, Kathmandu offsets, microseconds, invalid and aware inputs and UTC conversion overflow. Another 500 UTC instants across five zones are checked to ensure the original instant remains a valid classification candidate.
- 99% measured combined statement/branch coverage. The module entry point is exercised in a subprocess; it is not counted in parent coverage. This is not a proof of complete behavioral coverage.
- Strict CSV and CLI checks cover multiline physical-line references, original-cell preservation, reserved/duplicate headers, malformed late records, byte/record bounds, UTF-8 BOM, an explicit legacy codec, staging cleanup and a concurrent output-name collision that preserves the other writer's file.
- Ruff lint/security and formatting checks, wheel/sdist builds and pip dependency consistency are release gates. A fresh virtual environment installs the built source distribution and runs the installed CLI outside the checkout, checking real mixed-result report contents.
- pip-audit found no known vulnerabilities in the installed third-party tooling/runtime dependency environment at check time. The only runtime dependency is separately installed tzdata. Its installed Apache 2.0 notices were reviewed and retained in THIRD_PARTY.md; that notice is also shipped in the wheel. This does not audit Python itself or prove absence of vulnerabilities.

Independent source review checked that UTC candidates are deduplicated by instant, every candidate roundtrips exactly, precision is never silently truncated, timezone data comes from the versioned package, unsafe resource keys cannot escape the package and malformed files cannot publish a partial report. CI independently runs Python 3.10/3.13 on Linux/macOS/Windows; consult the actual run before relying on cross-platform results.

The release cannot determine intended folds, invent missing timezone context or guarantee future timezone politics. Atomic non-overwriting publication requires a hard-link-capable filesystem; unsupported destinations return an IO error. No automatic correction, in-place rewrite or cloud upload is implemented.
