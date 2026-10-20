# Core refactor change report

## Outcome and architecture

Work is on refactor/core, based on verified stable commit d1664ea. main,
origin/main and the three experimental branches remain at that commit. Existing
worktrees are preserved. No push, merge, deletion service, model change, migration,
or production database access was performed.

Previously the CLI exposed five separate mutation commands, services repeated
lookup/event/commit/rollback code, engines were recreated per session, and
validation failure transaction behavior varied. Now CLI input/rendering delegates
to create/read/update/export operations in services.py. rules.py owns normalization
and lifecycle checks; errors.py defines expected domain failures; database.py owns
path/engine/session construction; exporting.py remains the XLSX renderer. Core
imports no Typer, Rich, Textual or PySide6. No generic framework or repository layer
was introduced.

## Service contract for all three interfaces

| Operation | Parameters and return |
| --- | --- |
| create_application | Existing keyword metadata; returns Application with initial event |
| list_applications | Optional company/status/category AND filters; returns list[Application] ordered by date/ID |
| get_application | Positive integer ID; returns Application or None |
| update_application | ID, metadata mapping, optional oa/interview/activity_note/status/event_date; returns Application |
| export_application_data | Path and same filters, optional overwrite; returns (application count, event count) |

Editable metadata: company, role_title, category, location, work_modality,
job_type, source, application_date, job_id, notes. Omitted keys are unchanged;
None or whitespace clears optional location/job_id/notes. Other required values
must be nonblank strings or canonical controlled choices. Calendar dates must be
Python date objects (not datetime/string). IDs must be positive integers.
Unknown/read-only metadata fields and empty updates are rejected.

Writers own the **entire supplied session transaction**: one commit on success,
rollback on any validation/retrieval/persistence exception. Use a dedicated session
per operation; do not mix unrelated pending ORM edits or wrap writers in an outer
transaction intended to commit later. Reads/export never commit. Results load
history in event-date/ID order before return and remain readable after session
closure; they are ORM objects, not live subscriptions. Re-read for fresh data.

ValidationError and ApplicationNotFound derive from JobTrackError and ValueError.
Database exceptions and filesystem failures retain their original types so each
interface can report/retry appropriately. get returns None for an absent valid ID;
updates raise ApplicationNotFound. Export rejects invalid suffixes/existing files
unless overwrite is enabled. Export rendering stays outside application services.

The specialized change_status, record_oa, record_interview, edit_role_notes and
record_note functions remain thin compatibility adapters. Status and role-note
adapters return Application; milestone and activity adapters return ApplicationEvent.

```python
from jobtrack.database import create_session
from jobtrack.services import update_application
from jobtrack.errors import JobTrackError

try:
    with create_session() as session:
        application = update_application(
            session, 1, metadata={"notes": "Role description"},
            interview=True, activity_note="Panel interview", status="Offer",
        )
    # Render the loaded application and application.events in the chosen UI.
except JobTrackError as error:
    # Present str(error) using the interface's error controls.
    pass
```

CLI, Textual and PySide6 should collect inputs, call these same operations, and
render results. GUI/TUI background workers must create their own sessions; never
share a Session across threads. Use rules constants for choice controls. Only
initialize_database creates tables. Explicit database_path arguments permit test
or alternative storage without resolving the production path. Future interfaces
can adopt these commits when authorized; their worktrees were not modified.

## Behavior preserved and intentional changes

- Preserved Applied -> Offer/Rejected/Withdrawn and terminal restrictions; no reopen.
- Preserved OA received prerequisite, duplicate prevention and repeated interviews.
- Preserved role-note replacement without events and activity notes after closure.
- Preserved backdated events: prerequisite means an existing received milestone,
  not a restriction on supplied dates. History remains date/ID ordered.
- Preserved filtering, literal wildcard matching, XLSX sheets/style/literal text,
  and the unchanged application/event tables.
- Added metadata editing and atomic combinations. Milestones execute before a
  terminal status in the same update. Failure in any category rolls back all.
- Editing application_date corrects metadata only; the original creation event is
  historical and remains unchanged. No new metadata audit event is invented.
- Unified validation rollback and explicit type/domain errors. Results load history
  eagerly, including for lists, so they work after the session closes.
- Public status/oa/interview/edit/log commands are removed; use update flags or its
  guided categories. Blank optional metadata also clears it; explicit --clear-notes,
  --clear-location and --clear-job-id flags are provided. Event dates can be supplied.
- Engines are reused per resolved path. Core export errors no longer mention CLI flags.

## Files and redundancy

Modified: services.py (shared writes, retrieval, events, export orchestration),
rules.py (domain errors/type validation), database.py (engine reuse, explicit paths),
exporting.py (interface-neutral errors), cli.py (one update command, shared export,
service-ordered history), README.md (usage/development), pyproject.toml (test extra
and pytest configuration), .gitignore (pytest cache).

Added: errors.py, tests/conftest.py, tests/test_core.py, tests/test_cli.py,
docs/core-audit.md, and this report. No files or schema objects removed. Removed
five public command implementations and repeated writer transaction/lookup/event
blocks. Preserved meaningful compatibility entry points and lifecycle rules.

## Validation

The initial audit/design and 9 passing characterization tests were committed
before service changes. Core changes then passed 24 tests. CLI integration and
additional cases produce **52 passing tests** with:

```
.venv\Scripts\python.exe -m pytest -q
```

Coverage includes creation and initial event, required/controlled validation,
terminal statuses, OA prerequisites/duplicates, multiple interviews, role/activity
notes, historical ordering, combined filters, XLSX content and overwrite behavior,
metadata corrections, atomic combined updates, injected event-write rollback,
validation rollback, usable detached results, explicit database paths, all guided
update categories, CLI flags/errors, removed commands, add/list/show/export/db,
and UI-import independence. All database tests use temporary or in-memory SQLite;
a global fixture rejects production path resolution. Unchanged models were also
verified against the baseline with git diff. git diff --check is clean.

## Remaining architectural concerns

The existing schema has no database uniqueness constraint for OA milestones and
no optimistic version column. Sequential service calls are validated, but strong
multi-process concurrency guarantees remain outside this refactor. Coordinate
writes if multiple interfaces run concurrently; revisit constraints/versioning only
with an explicit migration need. No dates are inferred or historical data repaired.

Loaded history increases list memory use; pagination/summary queries can be added
when actual data size requires them. Engine caching assumes a small number of
storage paths over the process lifetime. Services deliberately own commits; callers
needing multi-application transactions would require an explicit future contract.
XLSX overwrite retains the existing direct file-write behavior, without crash-safe
replacement guarantees. These limitations do not require schema or UI work here.
