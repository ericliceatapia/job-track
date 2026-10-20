# Amendment: simplified Online Assessment workflow

This amendment supersedes explicit OA Received/Completed choices and the former
absence of OA chronology checks in the core-refactor specification.

## Interaction and core contract

Expose one **Online Assessment** activity within Update. The CLI uses `--oa` or
its guided category; TUI/desktop should expose one equivalent action. Interfaces
must not ask users to select Received versus Completed.

1. Call `propose_online_assessment(session, id, event_date=optional_date)`.
2. Core reads persisted status and OA history without flushing or committing.
3. Render the returned proposal using this mapping:

| Core event_type | Interaction |
| --- | --- |
| OA_RECEIVED | Record online assessment received? |
| OA_COMPLETED | Mark online assessment completed? |
| None | Online assessment already completed. |

4. On confirmation only, call `update_application` with `oa=True`,
   `expected_oa=proposal.event_type`, and `event_date=proposal.event_date`.
5. Cancellation makes no write call. CLI cancellation cancels the entire combined
   update, including metadata. A complete assessment similarly returns without
   applying other flags; run a separate update for those changes.
6. Recording rechecks status/history/date. If the expected milestone differs from
   the current next milestone, reject the entire update and request a new proposal.
   A direct update after completion raises ValidationError with the completed
   message; the read-only proposal lets interfaces report completion normally.

```python
with create_session() as session:
    proposal = propose_online_assessment(session, application_id, event_date=day)
# Display a message or request confirmation in the chosen interface.
# If confirmed, open a fresh session and retain the proposal's date/type:
with create_session() as session:
    application = update_application(
        session, application_id, oa=True,
        expected_oa=proposal.event_type, event_date=proposal.event_date,
    )
```

The example's second call must only run after confirmation of a non-None event_type.
No session should be kept across asynchronous GUI dialogs. Core offers no UI prompts
and does not choose how an interface renders the proposal.

## Rules and compatibility

- No receipt: propose OA_RECEIVED. Receipt without completion: propose OA_COMPLETED.
- Receipt and completion: report complete; never add another event.
- Offer, Rejected and Withdrawn reject OA proposals and writes, even if history is
  complete. Existing status restrictions take precedence.
- Optional event_date defaults to today's calendar date and must be a Python date.
- Receipt must be on/after application_date. Completion must be on/after both
  application_date and the recorded receipt date. Same-day milestones are valid.
  Dates need not follow unrelated interviews or notes. No new future-date rule.
- An imported completion without receipt is invalid history, rejected without repair.
- OA_RECEIVED/OA_COMPLETED remain distinct stored/displayed/exported event types.
  No schema changes or historical data migration.
- The existing record_oa compatibility adapter accepts its old action parameter
  internally as an expected milestone, but interfaces must use automatic proposals.
- Confirmation guards sequential stale proposals. Database-level uniqueness and
  simultaneous multi-process write serialization remain separate concerns.

## Verification

The isolated pytest suite now has 76 passing cases. Amendment coverage verifies
both automatic milestones, duplicate prevention, completed reporting, cancellation
with no timestamps/metadata/events changed, no proposal flush/commit, stale proposal
rejection, closed restrictions at each OA stage, historical and same-day dates,
rejection before application/receipt, malformed legacy history, and CLI prompts.
The original schema and experimental branch/worktree baseline remain unchanged.
