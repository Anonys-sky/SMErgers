# SMErgers

> Changes agreed in a job's WhatsApp group become approved, traceable changes, a new version of the quote for everyone, and a correct draft final bill. Built for small event companies first, and for any business that works job by job.

**Team VBall** · SDC Hackathon 2026, Domain 2: Orbyte Smart SME Challenge · SDG 8 (targets 8.2 and 8.3) · Licensed under Apache 2.0

| Resource | Link |
| --- | --- |
| GitHub repository | https://github.com/Anonys-sky/SMErgers |
| Pitch deck | https://claude.ai/artifact/E9Ha8YrDr2SKnbHsF4QFjx |

All data in this repository is synthetic. No real chat, person, client or company is used.

---

## The problem

In a small event company the quote is signed early, and then the job changes inside the WhatsApp group: 15 more guests, a bigger LED wall, the emcee staying an extra hour, two microphones on the night. Nobody turns those messages into a record. Everyone remembers a different version. At the end of the job someone rebuilds the final bill by scrolling the chat, extras go unbilled, and when the client says "I never agreed to that" there is nothing to show, so the owner often gives the money away.

This comes from a team member's experience at an event company, where it happened on almost every event. It is one person's account, not a survey.

## What SMErgers does

**Catch it.** SMErgers reads the job's WhatsApp group as messages arrive, so nobody exports anything. It groups messages into threads (a request and its replies) and works out what changed, by how much, at what price, and whether both sides agreed.

**Confirm it.** Each change goes to the right person. The project manager checks it, the owner signs off on large or unusual items, and the client confirms or disputes it on their own page. Each person is messaged when it is their turn.

**Sync it.** Every client confirmation creates a new version of the quote (v2, v3 and so on) and posts a summary back to the group, so everyone works from the same numbers. Only confirmed changes reach the draft bill, and every line links back to the messages it came from.

When something is unclear, SMErgers does not guess. A change with no price anywhere is marked "needs a price", a discount with no clear base goes to the owner, and a request nobody agreed to stays "discussed, not confirmed".

## Features

| Feature | What it does |
| --- | --- |
| Live from WhatsApp | Receives messages in Meta's official Cloud API webhook format, with signature checking and the verification handshake. The demo feeds a synthetic chat one message at a time. |
| Change finder | Rules that handle follow-ups ("and 1 at the lift lobby also"), recaps, withdrawn requests, "let me ask boss first", Malay and Chinese phrasing, per-unit prices and running totals. |
| Show in chat | Every change and bill line highlights the exact messages it came from. Clicking a message jumps to its change. |
| Approval by the right person | Named people from a company directory: the PM and the owner use the app; the client confirms on a phone-sized page opened from a WhatsApp link; finance downloads the CSV. The owner signs off at RM500 or more, on discounts, on unconfirmed items and on prices typed by staff. Enforced on the server, not only hidden in the page. |
| Quote versions and messages | Each confirmation makes a new quote version and posts it to the group. Approval and confirmation requests go to the next person. All of it, with the activity log, is on the job's History page. |
| Guided journey | A five-step guide on every job (messages arrive, PM checks, owner approves, client confirms, everyone in sync) says who acts next and hands over in one click. |
| Next time, quote it upfront | Counts from past jobs show what usually changes late in this kind of event and the one step that moves the decision into the quote, e.g. "the event ran past the planned end in 4 of 4 dinners: put overtime rates in the quote". |
| Draft final bill | The quote with adjusted quantities plus agreed changes, what is not on the bill yet and why, and a CSV for accounting software. A draft, never an invoice. |
| Activity log | Who did what, in which role, and when. Each entry is chained to the one before, so a later edit shows. |
| Job API | `GET /api/jobs/<id>` returns changes, approvals, bill totals, suggestions and the log, as a building block for Orbyte. |

## How it fits the Domain 2 journey

| Step in the brief | In SMErgers |
| --- | --- |
| Trigger | A message arrives in the job's WhatsApp group (webhook) |
| Connected data | The signed quote, the rate card, the client, the job and the company directory |
| Decision logic | Fixed, explainable rules find each change, its quantity and price, and whether both sides agreed |
| Human approval | PM checks; owner signs off on large or unusual items; client confirms |
| Visible outcome | Quote v2 posted to the group, the draft bill and CSV, and the activity log |

## Where AI fits, and where it does not

The chat-reading step has two readers behind one interface (`src/reader.py`):

- **Rules reader** (default): fixed, explainable rules. Fast, offline, and the fallback.
- **AI reader** (`SMERGERS_READER=llm`): a pre-trained language model, by default Llama 3.1 8B running locally through [Ollama](https://ollama.com). No API key, no internet, no training by us. It only reads: it finds the changes and cites the messages. Plain code then rejects any price that is not written in the cited messages or in the quote, sets every status itself, and falls back to the rules if the model is offline or answers badly. Approval and billing never use the model.

```bash
ollama pull llama3.1:8b
SMERGERS_READER=llm python src/main.py
```

Other OpenAI-compatible endpoints work through `SMERGERS_LLM_URL`, `SMERGERS_LLM_MODEL` and `SMERGERS_LLM_KEY`. On a laptop GPU the model takes about 2 minutes per chat, so the demo uses the rules by default.

The product creates its own training data: every approval, rejection and dispute is a human-checked label on real chat messages. After a pilot with real companies, that data can train a model to read messages and to make the "quote it upfront" suggestions. We do not train on made-up chats.

## Orbyte fit

SMErgers is a module for Orbyte's hub. It reuses Orbyte's clients and projects, directory and roles, approvals, eSign and audit trail, and adds one capability Orbyte does not have: turning chat into approved changes. The same engine runs a café renovation chat with only a different quote file. Interface assumptions are in [docs/orbyte-integration.md](docs/orbyte-integration.md).

---

## How WhatsApp is read

The product uses Meta's official WhatsApp Business (Cloud) API. The business number creates one group per job, the client and vendors join by invite link, and messages arrive by webhook.

- `POST /webhooks/whatsapp` accepts Meta's payload format and checks the `X-Hub-Signature-256` signature when `WHATSAPP_APP_SECRET` is set.
- `GET /webhooks/whatsapp` answers Meta's verification handshake using `WHATSAPP_VERIFY_TOKEN`.
- The live demo job sends synthetic messages through the same code ("Next message", "Play the rest").

Known limits of the official Groups API: at most 8 participants per group, and an Official Business Account is required. Chat export (.txt) remains as a fallback.

`whatsapp/bridge.js` is an optional local connector built on whatsapp-web.js for reading an existing group during team testing. It is an unofficial client and against WhatsApp's terms for production use, so it is not part of the product.

---

## Tech stack

| Layer | Technology |
| --- | --- |
| Web app | Python 3.12, Flask, server-rendered Jinja templates, one CSS file |
| Logic | Rules engine, approval workflow, quote versioning, suggestions (all Python) |
| Data | In-memory store for the prototype; synthetic JSON data |
| WhatsApp | Meta Cloud API webhook format; optional Node.js bridge for testing |
| Tests | pytest (113 tests); Node test runner for the bridge |
| Hosting and development | Replit |

## Project structure

```
.
├── data/                      Synthetic data only (see data/README.md)
│   ├── quotes/                Signed quote and rate card per job
│   ├── chats/                 WhatsApp-style chats
│   ├── answer_keys/           Hand-written expected changes, for scoring
│   ├── history/               Past jobs, for "quote it upfront" suggestions
│   ├── vendor_invoices/       Vendor invoice for a future vendor check
│   └── team.json              Company directory (stands in for Orbyte's Directory)
├── docs/
│   ├── results.md             Every accuracy run, with caveats
│   └── orbyte-integration.md  Interface assumptions and the WhatsApp design
├── src/
│   ├── main.py                Web app entry point (routes only)
│   ├── webhook.py             WhatsApp Cloud API webhook format and live ingestion
│   ├── chat_import.py         Chat parsing (exports and live messages)
│   ├── catalogue.py           Quote lines, rate card and the words that name them
│   ├── rules_extractor.py     Finds the changes agreed in a chat
│   ├── workflow.py            Approval flow, permissions, activity log
│   ├── sync.py                Quote versions and messages to the group and approvers
│   ├── bill.py                Matches confirmed changes to the quote, builds the draft bill
│   ├── suggest.py             Suggestions from past jobs
│   ├── evaluate.py            Scores the extractor against the answer keys
│   ├── store.py               Jobs, demo reset and the live demo feed
│   ├── whatsapp_bridge.py     Client for the optional local bridge
│   ├── schema.py              Shared data shapes
│   └── templates/, static/    Pages and styles
├── whatsapp/                  Optional local bridge (Node.js, team testing only)
├── submission/                Submission documents (see submission/README.md)
├── tests/                     pytest suite
├── .env.example  .replit  replit.md  requirements.txt  package.json  LICENSE
```

## Architecture

```
WhatsApp group ──webhook──► webhook.py ──► reader (rules or AI) ──► workflow ──► sync.py ──► group update, quote v2
   (.txt export ──► chat_import)              ▲                (PM ► owner ► client)        approval and confirm requests
                                 quote, rate card, directory                    │
                                                                                ▼
                                       suggest.py ◄── past jobs        bill.py ──► draft bill, CSV
                                                                                ▼
                                                                  activity log, GET /api/jobs/<id>
```

---

## How to run

### On Replit

1. Import this repository: **Create Repl → Import from GitHub**.
2. Optional: add `SECRET_KEY` in **Secrets** (see `.env.example`).
3. Click **Run**. The `.replit` workflow starts `python src/main.py` on port 5000.

### Locally

```bash
git clone https://github.com/Anonys-sky/SMErgers.git
cd SMErgers
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python src/main.py               # then open http://localhost:5000
```

### Tests and accuracy scores

```bash
python -m pytest
python src/evaluate.py
npm test                         # bridge conversion tests (needs Node.js)
```

### Optional local WhatsApp bridge (team testing only)

```bash
npm install
npm run whatsapp                 # then link a test number from /whatsapp
```

## Demo walkthrough (about 3 minutes)

The guide bar at the top of each job always says what happens next and who does it, and hands over to the next person with one button.

1. On the home page, click **Start the demo**. Press **Next message** a few times: messages arrive from the WhatsApp group and changes appear as people talk. Then press **Play the rest**.
2. You are Aisyah, the PM. Click **Show in chat** on the LED wall upgrade: the request, the price and the "ok go ahead" light up.
3. The wireless mics have no price anywhere, so they show **Needs a price**. Set RM320 (the owner must now approve it, because staff entered the price), then **Check all**.
4. Press **Continue as Daniel (Owner)**. Read **Next time, quote it upfront**, then approve.
5. Press **Open the client's link**: the phone-sized page the client sees from WhatsApp. Dispute the banners ("we asked for 2") and confirm the rest.
6. Press **Back to Aisyah**. In the chat, SMErgers has posted "quote version 2" to the group. Click **Show in chat** on the disputed banners: the client's own "2 more" and "and 1 at the lift lobby" settle it. Then open **Bill** and **History**.

---

## Results

Scored with `python src/evaluate.py` against hand-written answer keys. A change is fully right when both its status and its price match.

| Chats | Changes | Rules: fully right | Baseline: fully right |
| --- | --- | --- | --- |
| The chat the rules were built on | 10 | 10 | 3 |
| Three more chats by the same author | 20 | 20 | 5 |

Baseline: every message with an RM amount counts as a change.

**The first two rows are not accuracy figures.** The same person wrote the chats, the answer keys and the rules.

**Blind chats.** Three chats, their quotes and answer keys were written by separate AI agents that never saw the extractor, and committed before any scoring. Each reader was scored once ([Runs 2 and 3](docs/results.md)):

| Reader | Found | Fully right (status and price) | False changes |
| --- | --- | --- | --- |
| Baseline | 15 of 29 | 3 | 5 |
| Rules | 22 of 29 | 13 | 3 |
| AI reader | 28 of 29 | 18 | 1 |

That is 29 changes in synthetic chats, so it is a first independent check, not accuracy on real chats. The log lists where the AI reader is still wrong (for example, calling an unconfirmed change "ready"), which is why a person checks every change.

Fed one message at a time through the webhook, the live demo job ends with exactly the same 10 changes as reading the whole chat at once (tested).

## Business model

The owner pays, because the owner is the one giving money away; the PM and finance use it every day. Tiers, as hypotheses to test in a pilot:

| Tier | Price | Includes |
| --- | --- | --- |
| Capture | Free | One active job, find and list changes |
| Confirm | RM100 a month | Approvals, client confirmation links, group updates |
| Settle | RM250 a month | Draft bills, CSV, log export, suggestions, all jobs |

Usage pricing through Orbyte credits is the alternative. Break-even: Confirm costs RM1,200 a year, so recovering one forgotten RM1,200 extra a year pays for it.

## Privacy and boundaries

- **Synthetic data only.** Every chat, quote, company and person in this repository is invented and labelled.
- **No payments, filings or advice.** The bill is a draft for accounting software. Nothing is sent or paid. The record of what was agreed is not legal advice.
- **Sign-in is simulated,** as the brief allows: switch people with the menu at the top or the guide's hand-over button. Permissions are still checked on the server.
- **PDPA in a real deployment:** clients and vendors are told why the group is read; only messages linked to changes are kept; access is limited by role; a retention period is set; access and deletion requests are honoured. A pilot with real chats needs a legal review first.

## Known limits

- Rules understand the phrasing they were written for. New slang, typos and voice notes can be missed, which is why nothing reaches the bill without a person's check and the client's confirmation.
- Data is held in memory; a restart resets the demo.
- Messages to the group and to approvers are queued and shown on screen; delivering them needs the official WhatsApp API.
- Dates in chat exports are read day-first, as WhatsApp exports them in Malaysia.

## Roadmap

| Phase | What | Proof we will need |
| --- | --- | --- |
| Now | Prototype: live webhook, rules, approvals, quote versions, suggestions | Score on unseen chats; timed test of building the final bill by hand against SMErgers |
| Pilot | 3 to 5 event companies on the official WhatsApp API with consent; Orbyte approvals and eSign; a model trained on approvals | Hours saved per job, changes caught, disputes settled with a source |
| Grow | Renovation, agencies and print; vendor quote comparison; turning a client's photo into a change | Paying teams who stay |

---

## Tools we used

| Tool | How we used it |
| --- | --- |
| Replit | Development and running the app; `.replit` defines the run workflow. Replit Agent assisted with configuration and styling. |
| GitHub | This repository: Apache 2.0, small commits through the hackathon |
| RunPod | Not used: no GPU work (handbook section 9.4) |
| Claude and Replit Agent | AI coding assistants; declared in the Technical Tools Declaration |
| whatsapp-web.js | Optional local bridge for team testing only |

## Team VBall

- **Vincent Chew Wen Jie**, team leader ([@Anonys-sky](https://github.com/Anonys-sky))
- **Steven Elnathan Meliala**, WhatsApp connector (`whatsapp/`)
- **Looi Wan Wei**

## License

[Apache License 2.0](LICENSE)
