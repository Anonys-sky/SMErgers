# How OnRecord would fit Orbyte (interface assumptions)

The brief allows teams to create their own interface and API assumptions; we had no access to Orbyte. Everything below is an assumption, and in this prototype every Orbyte piece is simulated.

## What OnRecord adds

Orbyte already provides people, roles, approvals, eSign and an audit trail. OnRecord adds one capability it does not reproduce: **turning changes agreed in chat into approved records and a correct draft final bill**, for any business that works job by job (events first; renovation, agencies and print shops use the same flow).

## Mapping

| OnRecord needs | Orbyte piece we assume | In this prototype |
|---|---|---|
| The job and its client | Clients and projects | `data/quotes/*.json` |
| The signed quote and rate card | Project documents | Same JSON files |
| Who is PM, owner, client, finance | Directory, shared roles | "Viewing as" switch, checked server-side in `src/workflow.py` |
| Owner and client sign-off | Approvals, eSign | Approve and Confirm buttons |
| A record that cannot be quietly edited | Audit trail | Hash-chained log in `src/workflow.py` |
| Sending the bill out | Accounting and e-invoicing partners | CSV export of the draft bill; nothing is sent |

## Read-only API (built)

`GET /api/jobs/<job_id>` returns the job, every change found (with its approval state, price, reason and the ids of the chat messages it came from), the bill totals and the activity log with its integrity check.

In a real deployment this would sit behind Orbyte's platform authentication. It is open in the prototype so the demo can show it.

## Events we assume Orbyte would send (not built)

| Event | What OnRecord does |
|---|---|
| A chat export is attached to a project | Runs the extractor and lists the changes for the PM |
| A change is approved or confirmed in Orbyte Approvals or eSign | Moves the change to the next state and logs it |
| The project is closed | Produces the draft final bill for the accounting partner |
