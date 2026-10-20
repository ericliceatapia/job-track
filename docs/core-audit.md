# Core refactor audit and proposed design

## Baseline and inventory

Audited all tracked files at d1664ea (main and origin/main). The pre-existing
refactor/core branch also pointed to that commit and is reused. The CLI, TUI,
and desktop experimental branches/worktrees are preserved. No tracked automated
tests or manual test scripts exist; README gives installation and smoke commands.

- models.py: Application owns ApplicationEvent rows through application_id;
  ORM cascade is all/delete-orphan. Metadata, status, role notes, timestamps are
  on applications; dated milestones, status old/new values and activity notes
  are on events. No migrations exist. Preserve both tables unchanged.
- rules.py: case-insensitive canonical choices; trimmed required and optional
  text. Applied can become Offer, Rejected, Withdrawn; these are terminal.
  OA requires an active application, received before completed, one of each.
  Interviews require active status and may repeat. Notes may change after closure.
  Dates are supplied by callers; no chronological prerequisite is enforced.
- services.py: create plus initial event; list/get; six specialized mutations.
  Each writer commits independently and rolls back persistence errors. Validation
  occurs outside rollback blocks in several writers. Missing IDs raise ValueError
  for writes, while get returns None. Queries combine company substring (escaped
  SQL wildcards), canonical status/category with AND; date then ID ascending.
- database.py: production path is under the user's Local AppData. Every session
  creates another engine. Initialization creates missing tables only.
- exporting.py: Applications and History sheets, date/ID history order, literal
  user text (including formulas), job IDs as text, sizing, filters, frozen headers,
  overwrite protection. Relationship access requires an open session.
- cli.py: prompts and Rich rendering belong here. Repeated write/error adapters
  expose status/oa/interview/edit/log independently. History sorting and export
  query orchestration live in CLI. Metadata editing is currently absent.
- __init__.py is empty; pyproject contains runtime dependencies and CLI entry point;
  README describes installation; .gitignore excludes local DBs and exports.

## Proposed implementation

Keep models, rules, and XLSX renderer. Add domain validation/not-found errors
compatible with ValueError. A single transaction wrapper encloses validation,
retrieval, mutation, flush and commit; failures rollback. Writers own the supplied
session transaction, so callers use a dedicated session per operation. Do not
introduce repositories, UI dependencies, deletion, or migrations.

Provide create_application, list_applications/get_application, update_application,
and export_application_data. Update accepts a validated metadata mapping plus
optional OA, interview, activity note, and status changes in one atomic operation;
role notes are metadata. Apply milestones before terminal status so a final
interview and closure can be recorded together. Preserve specialized functions as
compatibility adapters with their existing return shapes. Return loaded application
objects, including sorted history, usable after session close. Export returns
application/event counts and reuses list filtering. Cache engines by explicit
SQLite path and allow isolated test paths without resolving production storage.

Replace redundant public commands with jt update [ID], supporting flags and a
guided category prompt. Keep add/list/show/export/db. Add metadata editing and
explicit nullable field clearing. No Textual or desktop implementation in this phase.

## Verification sequence

First commit characterization tests against unchanged services: creation, rules,
closed states, OA prerequisites/duplicates, repeat interviews, notes, filters,
XLSX, and rollback. Then implement core and CLI in separate local commits,
expanding tests for atomic combined updates, detached results, metadata validation,
CLI workflows, and database compatibility. All tests use temporary/in-memory
SQLite; never initialize or open the production database. Document intentional
contract changes and remaining concurrency limitations in the final report.


## Accepted amendment: simplified Online Assessment

The baseline observations above describe pre-refactor behavior. The
[Online Assessment amendment](online-assessment-amendment.md) supersedes the
original action-selection and OA date behavior: expose one activity, propose the
next milestone from stored history, confirm before writing, revalidate on write,
and enforce receipt/application and completion/receipt chronology. Preserve the
two event types and all terminal restrictions, without changing schema.
