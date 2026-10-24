# Scope and acceptance criteria

Audience: analysts and maintainers receiving CSV logs/exports containing local wall-clock timestamps. A complete workflow is file + explicit IANA zone(s) → CSV audit → inspect missing/repeated/invalid records → correct the upstream data using external evidence. No time is guessed, shifted or selected automatically.

Classification constructs fold=0 and fold=1 candidates, converts each to UTC and back, and retains only exact local roundtrips. Deduplicate by UTC instant and sort chronologically. Zero candidates means nonexistent; one unique; two ambiguous. This handles half-hour transitions and whole skipped days without assuming an hour-long DST transition. Aware inputs are deliberately rejected: the tool audits naive wall clocks, not UTC conversions.

Read TZif resources explicitly from the installed tzdata package with validated relative zone keys. System zone files, host locale and TZ environment settings do not determine results. Record both tzdata package and IANA database versions. Cache at most 256 zones; stream data rows without retaining the full input/output. Bounds: 64 MiB actual bytes read, one million records by default, and Python csv's default field-size limit.

Strict CSV headers/record widths prevent silent field loss. Preserve original cell text and order, then add reserved audit columns, record index and physical starting line. Normalize output encoding/newlines to UTF-8/LF. Distinguish row-level problems (exit 1 with a complete report) from malformed CSV, configuration or IO failures (exit 2 without a published report).

Write to a same-directory temporary file, close/fsync it, then publish by hard link with no overwrite. Clean staging on success or ordinary errors. This requires a filesystem with hard-link support, such as typical NTFS/APFS/ext4 local storage; unsupported filesystems fail safely. Exclusive publication also protects against an output name created after the initial existence check. This is not a guarantee against concurrent input changes or an untrusted directory owner.

Acceptance: known folds/gaps in New York, a half-hour fold/gap in Lord Howe, Samoa's skipped date, quarter-hour offsets, microseconds, invalid/aware/date-only inputs, malicious zone keys, unknown zones, extreme date overflow, duplicate/reserved headers, ragged/quoted/multiline rows, stream limits, cleanup after late parse errors, existing-output/race refusal and a fresh installed CLI flow.
