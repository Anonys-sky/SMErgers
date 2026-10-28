# How SMErgers would fit Orbyte (interface assumptions)

The brief allows teams to create their own interface and API assumptions; we had no access to Orbyte. Everything below is an assumption, and in this prototype every Orbyte piece is simulated.

## What SMErgers adds

Orbyte already provides people, roles, approvals, eSign and an audit trail. SMErgers adds one capability it does not reproduce: **turning changes agreed in chat into approved records and a correct draft final bill**, for any business that works job by job (events first; renovation, agencies and print shops use the same flow).

## Mapping

| SMErgers needs | Orbyte piece we assume | In this prototype |
|---|---|---|
| The job and its client | Clients and projects | `data/quotes/*.json` |
| The signed quote and rate card | Project documents | Same JSON files |
| Who is PM, director, client, finance | Directory, shared roles | "Viewing as" switch, checked server-side in `src/workflow.py` |
| Director and client sign-off | Approvals, eSign | Approve and Confirm buttons |
| A record that cannot be quietly edited | Audit trail | Hash-chained log in `src/workflow.py` |
| Sending the bill out | Accounting and e-invoicing partners | CSV export of the draft bill; nothing is sent |

## Read-only API (built)

`GET /api/jobs` lists every job with its approval counts and its own director sign-off limit, so another module can find a job before opening it. `GET /api/jobs/<job_id>` returns the job, every change found (with its approval state, price, reason and the ids of the chat messages it came from), the bill totals and the activity log with its integrity check.

In a real deployment this would sit behind Orbyte's platform authentication. It is open in the prototype so the demo can show it.

## Events we assume Orbyte would send (partly built)

| Event | What SMErgers does |
|---|---|
| A chat export is attached to a project | Runs the extractor and lists the changes for the PM |
| A change is approved or confirmed in Orbyte Approvals or eSign | Moves the change to the next state and logs it |
| The project is closed | Produces the draft final bill for the accounting partner |

## WhatsApp (built as a simulated webhook)

The product reads each job's WhatsApp group through Meta's official WhatsApp Business (Cloud) API:
the business number creates one group per job, the client and vendors join by invite link, and
messages arrive by webhook. `POST /webhooks/whatsapp` accepts Meta's payload format, checks the
`X-Hub-Signature-256` signature when `WHATSAPP_APP_SECRET` is set, and `GET` answers Meta's
verification handshake with `WHATSAPP_VERIFY_TOKEN`.

Assumption to verify: we read the group from a `group_id` field on each message.
Known limits of the official Groups API: at most 8 participants per group; an Official Business
Account is required. Messages SMErgers sends (approval requests, confirmation requests, quote
version updates) are queued in an outbox; the API would deliver them.
