# Client Demo Script (6–8 minutes)

Showcase IDs:

- Sarah Lee-Kim: `HCP-000123`
- Lakeshore affiliation review: `REV-SARAH-AFF`
- Priya Sharma (Chicago cardiology): `HCP-000201`
- Priya Sharma (Houston endocrinology): `HCP-000202`
- Unresolved Priya note case: `REV-PRIYA-AMB`
- Linkable unassigned record: `REV-LINK-UNASSIGNED` / `HCP-000801`

Reset before a clean presentation (backend stopped):

```powershell
cd backend
python scripts/reset_demo.py --confirm RESET
```

Then start backend + frontend. No LLM key or external service is required.

## Sequence

1. **Overview (45s)** — Open `/overview`. Explain Source Doctor Entries vs Golden Doctor Profiles. Point at Linked Records and Consolidated Duplicate Entries tooltips. Note the shell badge: Demo data • Simulated analysis.

2. **Search previous name (60s)** — Go to Golden Records. Search `Sarah Lee`. Open **Sarah Lee-Kim** (`HCP-000123`). Show aliases including previous name and abbreviation.

3. **Linked records (60s)** — Expand profile or stay in drawer. Open Linked Records. Compare invoice name `Dr. Sarah Lee`, registration `S. Lee`, and credential `Dr. Sarah Lee-Kim`. Note the speaker invoice is a supporting transaction, not a duplicate doctor entry. NPI shows Not verified.

4. **History + citation (75s)** — Open History & Timeline. Find **Name change documented**. Click View evidence for the credential update. Confirm the quoted text matches the highlighted document block on DOC-003.

5. **Pending affiliation (60s)** — Return to Profile Summary. Show Oakridge as current/known affiliation and Lakeshore as proposed. Open the practice-change form evidence (DOC-004).

6. **Approve live (75s)** — Open Review Center → `REV-SARAH-AFF` (or from pending update link). Approve affiliation update with a reason. Confirm Lakeshore becomes primary, Oakridge remains historical observation without an invented end date, and audit/history refresh.

7. **Same-name separation (45s)** — Search `Priya Sharma`. Open both Chicago and Houston profiles. Emphasize different credentials/locations keep masters separate.

8. **Steward unresolved case (45s)** — Open `REV-PRIYA-AMB` or Review Center pending ambiguity. Explain the name-only note stays unresolved until a steward has corroborating evidence.

9. **Close (20s)** — Reiterate: sources and match outcomes are synthetic/simulated; the UI and API workflow run end to end on local demo state.
