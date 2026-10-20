# JobTrack

A local command-line job application tracker for Windows.

## Install

1. Install [Python 3.14](https://www.python.org/downloads/windows/) and [Git for Windows](https://git-scm.com/download/win). Enable the Python PATH option during installation, then open a new PowerShell window.
2. Install JobTrack:

   ```powershell
   py -3.14 -m pip install "git+https://github.com/ericliceatapia/job-track.git"
   ```

3. Initialize your database and start tracking:

   ```powershell
   jt db
   jt add
   jt list
   jt --help
   ```

If `jt` is not recognized, add the Scripts directory shown in pip's installation warning to your user PATH, then reopen your terminal. No repository clone or virtual-environment activation is required.

Your data stays on your machine at `%USERPROFILE%\AppData\Local\JobTrack\jobtrack.db`.

## Update

```powershell
py -3.14 -m pip install --upgrade "git+https://github.com/ericliceatapia/job-track.git"
```

## Core operations and CLI

The public commands are `jt add`, `jt list`, `jt show ID`, `jt update [ID]`,
`jt export PATH.xlsx`, and `jt db`. Run `jt --help` or `jt update --help`.
`jt update` prompts for an ID and update category when omitted.

```powershell
jt update 1 --company "New company" --role-title "Data Analyst"
jt update 1 --notes "Role description"
jt update 1 --clear-notes
jt update 1 --oa received
jt update 1 --oa completed --event-date 2026-10-20
jt update 1 --interview --activity-note "Panel interview"
jt update 1 --status Offer
jt export applications.xlsx --company Acme --status Applied
```

Combine update flags to save changes atomically. Use `--clear-location` and
`--clear-job-id` for optional metadata. Status, assessment, interview, role-note,
and activity-note updates now all use `update`; the former `status`, `oa`,
`interview`, `edit`, and `log` commands have been removed.

## Development and interface integration

```powershell
py -3.14 -m pip install -e ".[test]"
py -3.14 -m pytest -q
```

Tests use isolated SQLite storage and prohibit production database resolution.
The CLI, future Textual TUI, and future PySide6 GUI should call the same
`jobtrack.services` operations with a dedicated session per operation. See the
[core audit](docs/core-audit.md) and [change report/service contract](docs/core-refactor-report.md).
