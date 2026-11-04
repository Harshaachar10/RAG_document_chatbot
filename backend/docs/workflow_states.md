# Workflow States

## Review status

- `pending` — awaiting steward action
- `deferred` — paused; Resume returns to pending
- `completed` — final decision recorded; cannot be re-decided

## Resolution status (source records)

- `linked`
- `review_required`
- `unresolved`
- `identifier_conflict`

## Decision actions

| Case type | Actions |
| --- | --- |
| possible_duplicate | link_records, keep_separate, defer |
| same_name_ambiguity | select_candidate, leave_unresolved, defer |
| identifier_conflict | leave_unresolved, defer |
| name/address/affiliation_update | approve_update, reject_update, defer |

Link records attaches an eligible unassigned identity entry to an existing master. Master-to-master merge is not implemented in this mock phase.
