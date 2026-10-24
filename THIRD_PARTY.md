# Third-party dependency notices

Original localtime-audit source is MIT licensed. It depends on the separately installed [tzdata](https://github.com/python/tzdata) package; no tzdata source or database files are copied into this repository or wheel.

The checked tzdata 2026.5 distribution declares Apache Software License 2.0 and carries these notices:

- Copyright (c) 2020, Paul Ganssle (Google)
- Copyright (c) 2026, Stan Ulbrych

Its license and full Apache terms are included in its installed distribution (`tzdata-*.dist-info/licenses/`). The database originates from [IANA's Time Zone Database](https://www.iana.org/time-zones). Preserve upstream notices when redistributing dependencies. This project's MIT license does not relicense third-party material. Review the notices in the exact dependency version you redistribute.

Dependency data is read through Python's standard-library zoneinfo implementation. Development-only tools are listed separately in requirements-dev.txt and are not bundled in release wheels.
