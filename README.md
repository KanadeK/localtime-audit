# localtime-audit

Find local timestamps that cannot safely be assigned a single UTC instant. Audit a CSV with explicit IANA zones and get **unique, ambiguous, nonexistent or invalid** per-record results, including both UTC candidates for repeated clocks. Original fields stay intact; nothing is silently shifted or selected.

For analysts reviewing logs, exports and imports around clock changes. Python 3.10+, local processing, one data-only dependency: `tzdata`. [中文说明](README.zh-CN.md).

## Install

```sh
git clone https://github.com/KanadeK/localtime-audit.git
cd localtime-audit
python -m venv .venv
```

Activate with `source .venv/bin/activate` on Linux/macOS or `.venv\Scripts\Activate.ps1` in PowerShell:

```sh
python -m pip install .
localtime-audit --version
```

The command also works as `python -m localtime_audit` after installation. Source checkouts and GitHub release archives/wheels are supported; this is not a claim of PyPI publication.

## Audit a file

```sh
localtime-audit examples/clocks.csv --column local_time --zone-column zone --output audit.csv --format json
```

This intentionally exits **1** and writes a complete report: four records, two unique, one ambiguous and one nonexistent. For New York's repeated `2024-11-03 01:30:00`, the candidates are `2024-11-03T05:30:00Z` and `2024-11-03T06:30:00Z`. Its missing `2024-03-10 02:30:00` has no candidate. These results indicate a need for upstream evidence; the tool does not pick the intended instant.

For one zone across the entire file:

```sh
localtime-audit examples/unique.csv --column local_time --zone Asia/Shanghai --output unique-audit.csv
```

This exits 0. The first event maps to `2024-01-01T00:00:00Z`. Choose a new output name on reruns: existing files, directories and symlinks are always refused. The input is never modified.

## Input and report contract

- Timestamp text: `YYYY-MM-DD HH:MM[:SS[.ffffff]]` or uppercase `T` separator, at most six fractional digits. No date-only inference, surrounding whitespace, leap seconds or silent nanosecond truncation.
- Input clocks must be **naive**: a `Z` or numeric UTC offset produces an `invalid / aware_input` row. Use an ordinary timezone converter if your inputs already identify instants.
- Supply exactly one `--zone IANA/Name` or `--zone-column NAME`. A bad constant zone is a configuration error; invalid/unknown per-row zones are row diagnostics. No host timezone is inferred.
- UTF-8 with optional BOM by default. Use `--encoding cp1252` for a known legacy encoding. `--delimiter comma|tab|semicolon` sets both input and output delimiter.
- Headers must be nonempty and unique, with no edge whitespace. Ragged/malformed rows and NUL characters fail the file. Empty physical records are ignored. Quoted multiline fields are supported.
- Stream up to 64 MiB of actual input bytes and 1,000,000 records by default; `--max-rows N` adjusts the latter. Individual CSV fields also obey Python's default csv field-size limit. Only 256 timezone objects are cached.

The output preserves original field order and cell values, then adds:

| Column | Meaning |
|---|---|
| `audit_record`, `audit_line` | 1-based data-record index and original physical start line |
| `audit_status`, `audit_reason` | Classification and machine-readable reason such as `clock_fold`, `clock_gap`, `invalid_datetime`, `aware_input`, `empty_zone` or `unknown_zone` |
| `audit_zone` | Explicit zone used for the row |
| `audit_utc_first`, `audit_utc_second` | UTC candidates in chronological order; second is populated only for ambiguous clocks |
| `audit_offset_first`, `audit_offset_second` | UTC offsets for the candidates, including historical seconds when relevant |
| `audit_tzdata`, `audit_iana` | Installed tzdata package and IANA rule versions |

These generated names are reserved; already audited input is refused rather than overwritten. `unique` rows have one candidate; ambiguous rows have two; nonexistent and invalid rows have none. A header-only input produces an empty report. Output is UTF-8 without BOM and LF, with original cells kept as data; this is a diagnostic copy, not a correction to the source.

`--format json` affects the **stdout summary**, which includes counts and rule versions but no source cell values. The detailed output is always CSV. The default stdout summary is one line.

| Exit | Meaning |
|---|---|
| 0 | Complete report; every record is unique (or no data records) |
| 1 | Complete report contains ambiguous, nonexistent or invalid rows |
| 2 | Argument, malformed-input, configuration or IO error; no report published by this invocation |

Reports are staged in the destination directory and published with an atomic hard link that cannot replace an existing name, including one created concurrently. Use a filesystem supporting hard links (ordinary NTFS/APFS/ext4 local storage). FAT/exFAT or some network filesystems may refuse publication; use a supported local destination and copy the completed report afterward. Normal errors remove staging files; a forcibly killed process can leave a `.localtime-audit-*.tmp` file for manual cleanup.

## Why not just localize a dataframe?

[pandas `tz_localize`](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.tz_localize.html) already handles ambiguous/nonexistent policies and is a good choice inside a Python pipeline. This CLI supplies an explicit CSV review workflow, original line references, both candidate instants and a CI-friendly exit code without dataframe code or a guessed policy.

Classification uses UTC roundtrips for both [PEP 495 folds](https://peps.python.org/pep-0495/); it does not assume every clock change is one hour. Tests cover Lord Howe's half-hour change and Samoa's skipped day. Rules are always read directly from the **installed tzdata package**, not from differing host databases. See [design](docs/DESIGN.md) and [dependency notices](THIRD_PARTY.md).

## Limits, privacy and maintenance

Version 0.1.0 cannot determine which repeated instant an event intended, recover absent timezone context, validate a log against real-world evidence or predict future political rule changes. Date arithmetic is limited to Python's year 1–9999/microsecond range; UTC conversion overflow is reported as invalid. Results can change when timezone data changes; retain the reported rule version with your evidence. Pin `tzdata` yourself when a reproducible rule snapshot is required.

No telemetry, uploads, external APIs or network requests occur during processing. Installation/dependency updates may use the package index. Detailed reports reproduce private source data; inspect them before sharing. Run against a stable input on a trusted filesystem. This release supports regular files, not stdin or an in-place rewrite.

For development commands see [CONTRIBUTING](CONTRIBUTING.md); CI tests Linux, macOS and Windows on Python 3.10/3.13 with read-only repository permissions. Security reports follow [SECURITY.md](SECURITY.md).

Uninstall with `python -m pip uninstall localtime-audit`. After deactivation, remove your virtual environment and generated reports/staging files as needed. pip may retain the separately installed tzdata dependency; deleting a dedicated environment cleans it up without affecting other projects.

Original source is [MIT licensed](LICENSE). tzdata remains under its upstream license; it is installed separately and is not bundled or relicensed by this project.
