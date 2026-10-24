# SMErgers

> Changes agreed in a job's WhatsApp group become approved, traceable changes, a new quote version for everyone, and a correct draft final bill. Built for small event companies first, and for any business that works job by job.

**Team VBall** · SDC Hackathon 2026 · Domain 2: Orbyte Smart SME Challenge · SDG 8 (targets 8.2 and 8.3) · [Apache License 2.0](LICENSE)

All data in this repository is synthetic. No real chat, person, client or company is used.

## Contents

| Section | What it covers |
| --- | --- |
| [Team information](#team-information) | Team, domain and SDG track |
| [Links](#links) | Repository, live prototype, deck, video, RunPod endpoint |
| [Overview](#overview) | The problem, the solution, the Domain 2 journey, Orbyte fit |
| [Quick start](#quick-start) | Run the app on Replit or locally in a few minutes |
| [Key features](#key-features) | What the prototype does |
| [Demo walkthrough](#demo-walkthrough) | A three-minute guided tour |
| [Where AI fits](#where-ai-fits) | Rules reader, AI reader, and the guards around the model |
| [Configuration](#configuration) | Environment variables |
| [API and webhook](#api-and-webhook) | Job API and WhatsApp webhook reference |
| [Tech stack](#tech-stack) | Languages, frameworks and services |
| [Project structure and architecture](#project-structure-and-architecture) | Folders and data flow |
| [Testing and results](#testing-and-results) | How to run the tests, and the measured accuracy |
| [How we use Replit](#how-we-use-replit) · [How we use RunPod](#how-we-use-runpod) | Hosting and GPU use, with proof of use |
| [Business model](#business-model) | Who pays, pricing tiers |
| [Privacy, boundaries and limits](#privacy-boundaries-and-limits) | Synthetic data, PDPA, known limits |
| [Challenges and learnings](#challenges-and-learnings) · [Future improvements](#future-improvements) | What we learned and what is next |
| [Contributing](#contributing) | Workflow and conventions |
| [Team](#team) · [Submission documents](#submission-documents) | Who built it, and where the proposal and proofs are |
| [License and acknowledgements](#license-and-acknowledgements) | Apache 2.0 and third-party notices |

---

## Team information

| Field | Details |
| --- | --- |
| Team name | VBall |
| Team domain | Domain 2: Orbyte Smart SME Challenge |
| SDG track | SDG 8, targets 8.2 and 8.3 |
| Team leader | Vincent Chew Wen Jie |
| Number of members | 3 |

## Links

| Resource | Link |
| --- | --- |
| GitHub repository | https://github.com/Anonys-sky/SMErgers |
| Replit project | (template) |
| Live prototype | (template) |
| RunPod endpoint | Serverless vLLM, endpoint ID `2y90x5ojwpgxnh` (the API key is kept in Replit Secrets) |
| Slide deck | https://claude.ai/artifact/E9Ha8YrDr2SKnbHsF4QFjx |
| Demo video (YouTube) | (template) |

---

## Overview

### Problem

In a small event company the quote is signed early, and then the job changes inside the WhatsApp group: 15 more guests, a bigger LED wall, an extra hour of overtime, two microphones on the night. Nobody turns those messages into a record, so at the end of the job someone rebuilds the bill by scrolling the chat, extras go unbilled, and when the client says "I never agreed to that" there is nothing to show. The owner often gives the money away. This comes from a team member's experience at an event company, where it happened on almost every event; it is one person's account, not a survey. For published context, Malaysian construction studies report that 89% of projects run over cost, typically by 5 to 10%, with variation orders a leading cause (Kamaruddeen, Chang and Wahi, 2020, as cited in *Research in Management of Technology and Business* 5(2), 2024). No public data exists for event companies.

### Solution

- **Catch it.** SMErgers reads the job's WhatsApp chat and works out what changed, by how much, at what price, and whether both sides agreed.
- **Confirm it.** The project manager checks each change, the project director signs off on large or unusual items, and the client confirms or disputes on their own phone-sized page.
- **Sync it.** Every confirmation creates a new quote version (v2, v3 and so on) and posts a summary back to the group. Only confirmed changes reach the draft bill, and every line links to the messages it came from.

When something is unclear, SMErgers does not guess: a change with no price is marked "needs a price", a discount goes to the project director, and a request nobody agreed to stays unconfirmed.

### How it fits the Domain 2 journey

| Step in the brief | In SMErgers |
| --- | --- |
| Trigger | A message arrives in the job's WhatsApp group (webhook), or a chat export is imported in the prototype |
| Connected data | The signed quote, rate card, client, job and company directory |
| Decision logic | Rules, or an AI reader for messy chats, find each change, its quantity and price, and whether both sides agreed |
| Human approval | PM checks; project director signs off on large or unusual items; client confirms |
| Visible outcome | Quote v2 posted to the group, the draft bill and CSV, and the activity log |

### Orbyte fit

SMErgers reuses Orbyte's clients and projects, directory and roles, approvals, eSign and audit trail, and adds one capability Orbyte does not have: turning chat into approved changes. The same engine runs a café renovation chat with only a different quote file. Interface assumptions are in [docs/orbyte-integration.md](docs/orbyte-integration.md).

---

## Quick start

Requirements: Python 3.12. Node.js is only needed for the optional WhatsApp bridge and two test files.

**On Replit:** import this repository (**Create Repl → Import from GitHub**) and click **Run**. The `.replit` workflow installs nothing extra and starts `python src/main.py` on port 5000. Add secrets only if you want the AI reader (see [Configuration](#configuration)).

**Locally:**

```bash
git clone https://github.com/Anonys-sky/SMErgers.git
cd SMErgers
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python src/main.py               # then open http://localhost:5000
```

The app opens on the Project manager workspace with four synthetic projects. Open **Annual Dinner 2026** to see a job; the [demo walkthrough](#demo-walkthrough) shows the full journey. State is kept in memory, and **Reset demo data** restores the samples.

## Key features

| Feature | What it does |
| --- | --- |
| Change finder | Handles follow-ups ("and 1 at the lift lobby also"), recaps, withdrawn requests, "let me ask boss first", Malay and Chinese phrasing, per-unit prices and running totals |
| Show in chat | Every change and bill line highlights the exact messages it came from |
| Role workspaces | Project manager, project director, client and finance views with their own queues, filters and checklists |
| Approvals enforced on the server | The director signs off at RM500 or more, on discounts, on unconfirmed items and on prices typed by staff; a client link cannot approve its own change |
| Client confirmation page | A phone-sized page opened from a WhatsApp link: confirm, or dispute with a reason |
| Quote versions | Each confirmation makes a new version and queues a summary for the group and the next approver |
| Guided journey | A five-step guide on every job says who acts next and hands over in one click |
| Draft final bill | Quote plus agreed changes, what is not on the bill yet and why, and a CSV; a draft, never an invoice |
| Activity log | Who did what, in which role, and when; each entry is chained to the one before, so an edit shows |
| Next time, quote it upfront | Counts from past jobs show what usually changes late and what to put in the quote |
| Add project | Create a project with its own quote and chat ([guide](docs/add-a-project.md)) |
| Job API and webhook | A read-only job API and Meta's Cloud API webhook format ([reference](#api-and-webhook)) |

## Demo walkthrough

About 3 minutes. The guide bar at the top of each job says what happens next and who does it.

1. In the Project manager overview, open **Annual Dinner 2026**. The chat is on the left and the changes found in it are on the right.
2. You are Aisyah, the PM. Click **Show in chat** on the LED wall upgrade: the request, the price and the "ok go ahead" light up.
3. The wireless mics have no price anywhere, so they show **Needs a price**. Set RM320 (the director must now approve it, because staff entered the price), then **Check all**.
4. Press **Continue as Daniel (Project Director)**. Read **Next time, quote it upfront**, then **Approve all**.
5. Press **Open the client's link**, the page the client sees from WhatsApp. Confirm all seven changes (RM3,860), or dispute one with a reason and it stays off the bill.
6. Press **Back to Aisyah**, then open **History**: SMErgers has posted "quote version 2" (RM38,390 when all seven are confirmed) to the group. Open **Draft bill** to see every line linked to its source.

To try the AI reader, open **Import chat**, choose `data/chats/blind_agent_a.txt` with its quote `q_blind_agent_a.json`, and tick **Read with the AI reader**.

## Where AI fits

The chat-reading step has two readers behind one interface (`src/reader.py`):

- **Rules reader** (default): fixed, explainable rules. Fast, offline, and the fallback.
- **AI reader**: Llama 3.1 8B Instruct on a RunPod GPU, used as it is with no training by us. It only reads: it finds the changes and cites the messages. Plain code then rejects any price not written in the cited messages or the quote, sets every status itself, and the rules take over if the model is unreachable. Three code guards sit on top of the prompt: a price promised "later" is never filled in from the quote, a colour or time swap with no price is logged as no cost, and a change whose last message is "let me ask my boss first" cannot be ready. Approval and billing never use the model.

Tick **Read with the AI reader** when importing a chat. Without RunPod keys the same reader uses a local [Ollama](https://ollama.com) server for development. After a quiet period the first AI request takes 2 to 3 minutes while the GPU worker starts.

Every approval and dispute is a human-checked label; after a pilot with real companies that data can train a model. We do not train on made-up chats.

## Configuration

All settings are environment variables; none is required to run the demo. On Replit, set them in **Secrets**. Never commit real values (`.env.example` lists them).

| Variable | Purpose | Default |
| --- | --- | --- |
| `PORT` | Port the app listens on | `5000` |
| `SECRET_KEY` | Signs the cookie that remembers which role you are viewing as (`SESSION_SECRET` is also read) | random at start-up |
| `SMERGERS_READER` | `llm` makes the AI reader the default for every job | `rules` |
| `RUNPOD_ENDPOINT_ID`, `RUNPOD_API_KEY` | Use the AI reader on a RunPod Serverless endpoint | unset: local Ollama |
| `SMERGERS_LLM_URL`, `SMERGERS_LLM_MODEL`, `SMERGERS_LLM_KEY` | Point the AI reader at any OpenAI-compatible endpoint | RunPod or Ollama |
| `SMERGERS_LLM_TIMEOUT` | Seconds to wait for the model | `300` |
| `WHATSAPP_VERIFY_TOKEN` | Token echoed back when Meta verifies the webhook | unset: verification refused |
| `WHATSAPP_APP_SECRET` | When set, every webhook call must carry a valid `X-Hub-Signature-256` | unset: not checked |
| `WHATSAPP_BRIDGE_URL`, `WHATSAPP_TIMEZONE` | Optional local test bridge (unofficial, not part of the product) | `http://127.0.0.1:3001`, system zone |

## API and webhook

**Job API.** `GET /api/jobs/<job_id>` returns one job as JSON. It is read-only and meant as a building block for Orbyte modules.

```bash
curl http://localhost:5000/api/jobs/annual-dinner
```

```json
{
  "job": { "id": "annual-dinner", "title": "Annual Dinner 2026", "client": "Sinar Demo Trading Sdn Bhd",
           "quote_id": "Q-2026-041", "simulated": true },
  "bill": { "quote_total": 34530.0, "agreed_in_chat_beyond_quote": 3540.0, "confirmed_changes": 0.0,
            "not_on_bill_yet": 3540.0, "draft_total": 34530.0 },
  "changes": [ { "key": "t1", "item": "Dinner package", "kind": "quantity_change", "qty_delta": 15,
                 "price": 1920.0, "found_as": "ready", "approval_state": "detected", "confidence": "high",
                 "quote_line": "L01", "evidence_message_ids": ["e7b3d420f6e7", "..."], "reason": "..." } ],
  "suggestions": [ { "title": "...", "seen_in": 4, "of_jobs": 4, "advice": "..." } ],
  "activity_log": { "intact": true, "entries": [ { "seq": 1, "action": "import", "hash": "...", "prev_hash": "start" } ] }
}
```

**WhatsApp webhook** (Meta Cloud API format):

| Method and path | Behaviour |
| --- | --- |
| `GET /webhooks/whatsapp` | Verification handshake: echoes `hub.challenge` when `hub.verify_token` matches `WHATSAPP_VERIFY_TOKEN`, otherwise 403 |
| `POST /webhooks/whatsapp` | Accepts Meta's payload (`entry → changes → value → messages`); returns 403 if `WHATSAPP_APP_SECRET` is set and the signature is invalid |

The group id is read from a `group_id` field on each message, which is our assumption because we had no API access; check it against Meta's Groups API documentation before going live. Messages are delivered to the job linked to that group; the default demo has no linked group, so chats come in by text export. The signature check and the handshake are covered by tests. Limits of the official Groups API: at most 8 participants per group, and an Official Business Account is required. The optional bridge (`npm run whatsapp`, then `/whatsapp`) uses an unofficial client for team testing only and is not part of the product.

## Tech stack

| Layer | Technology |
| --- | --- |
| Web app | Python 3.12, Flask, server-rendered Jinja templates, one CSS file |
| Logic | Rules engine, AI reader, approval workflow, quote versioning, suggestions (Python) |
| Data | In-memory store for the prototype; synthetic JSON data |
| AI / compute | Llama 3.1 8B Instruct on a RunPod Serverless vLLM endpoint (GPU); local Ollama for development |
| WhatsApp | Meta Cloud API webhook format; optional Node.js bridge for team testing only |
| Tests | pytest (290+ tests); Node test runner for the bridge and workspace filters |
| Hosting and development | Replit |

## Project structure and architecture

```
.
├── src/                 Flask app and logic (main.py, reader.py, rules_extractor.py, llm_extractor.py,
│                        workflow.py, sync.py, bill.py, suggest.py, webhook.py, ...), templates/, static/
├── data/                Synthetic quotes, chats, answer keys, past jobs, company directory (data/README.md)
├── tests/               pytest suite
├── docs/                results.md (every accuracy run), orbyte-integration.md, add-a-project.md
├── runpod/              Setup guide for the AI reader's RunPod endpoint
├── whatsapp/            Optional local bridge (Node.js, team testing only)
├── submission/          Submission documents (see submission/README.md)
└── .env.example  .replit  replit.md  requirements.txt  package.json  LICENSE
```

```
WhatsApp group ──webhook──► webhook.py ──► reader (rules or AI) ──► workflow ──► sync.py ──► group update, quote v2
   (.txt export ──► chat_import)              ▲                (PM ► director ► client)        approval and confirm requests
                                 quote, rate card, directory                    │
                                                                                ▼
                                       suggest.py ◄── past jobs        bill.py ──► draft bill, CSV
                                                                                ▼
                                                                  activity log, GET /api/jobs/<id>
```

## Testing and results

```bash
python -m pytest                              # 290+ tests: parsing, rules, permissions, billing, pages
python src/evaluate.py                        # score the rules against the answer keys
python src/evaluate.py --blind --ai           # also score the AI reader (needs a model endpoint)
npm test                                      # bridge conversion tests (needs Node.js)
node --test tests/workspace_filter.test.cjs   # workspace search and status filters
```

A change is fully right when both its status and its price match the hand-written answer key. The rules scored 10 of 10 and 20 of 20 on chats written by the same author as the rules, which is **not** an accuracy figure.

**Blind chats.** Three chats, their quotes and answer keys were written by separate AI agents that never saw the extractor, and committed before any scoring ([docs/results.md](docs/results.md), Runs 2 to 6):

| Reader | Found | Fully right | False changes |
| --- | --- | --- | --- |
| Baseline (any message with an RM amount) | 15 of 29 | 3 | 5 |
| Rules | 22 of 29 | 13 | 3 |
| AI reader on RunPod | 26 of 29 | **17** | 1 |
| AI reader after fixing the errors seen in that run (same chats, so optimistic, not independent) | 26 of 29 | 21 | 0 |

This is 29 changes in synthetic chats: a first independent check, not accuracy on real chats. The log lists where the AI reader is still wrong, which is why a person checks every change.

## How we use Replit

- **Development and hosting:** the Flask app runs on Replit; `.replit` starts `python src/main.py` on port 5000 and `requirements.txt` pins the dependencies.
- **Secrets:** `SECRET_KEY` and the AI reader's RunPod keys are set in Replit Secrets, never committed.
- **Assistance:** Replit Agent helped with configuration and styling, declared in the Technical Tools Declaration.
- **Proof of use:** `submission/SDC2026_VBall_Replit_POU.pdf`.

## How we use RunPod

The AI reader's model runs on a RunPod Serverless vLLM endpoint (Llama 3.1 8B Instruct, RTX 4090), not on Replit. RunPod runs the pre-trained model only: we train and fine-tune nothing.

- **When it runs:** only when a chat is imported with **Read with the AI reader** ticked; demo jobs and webhook messages use the rules.
- **Setup:** `RUNPOD_ENDPOINT_ID` and `RUNPOD_API_KEY` in Replit Secrets; steps and lessons in [runpod/README.md](runpod/README.md).
- **If it is down:** the rules read the chat and the page says so.
- **Proof of use:** `submission/SDC2026_VBall_Runpod_POU.pdf`.

## Business model

The owner pays, because the owner is the one giving money away; the project manager and finance use it every day. A B2B freemium subscription, with prices as hypotheses to test in a pilot:

| Tier | Price | Includes |
| --- | --- | --- |
| Capture | Free | One active job, find and list changes |
| Confirm | RM100 a month | Approvals, client confirmation links, group updates |
| Settle | RM250 a month | Draft bills, CSV, log export, suggestions, all jobs |

Break-even: Confirm costs RM1,200 a year, so recovering one forgotten RM1,200 extra a year pays for it. Usage pricing through Orbyte credits is the alternative.

## Privacy, boundaries and limits

- **Synthetic data only.** Every chat, quote, company and person here is invented and labelled.
- **No payments, filings or advice.** The bill is a draft for accounting software; nothing is sent or paid.
- **Sign-in is simulated,** as the brief allows; permissions are still checked on the server.
- **PDPA in a real deployment:** tell clients and vendors why the group is read, keep only messages linked to changes, limit access by role, set a retention period, honour access and deletion requests, and get legal review before a pilot.
- **Limits:** data is held in memory and resets on restart; group messages are queued and shown on screen, because delivery needs the official WhatsApp API; the rules and the AI reader can miss unusual phrasing, which is why nothing reaches the bill without a person's check and the client's confirmation.

## Challenges and learnings

- **Our first accuracy scores were contaminated.** One author wrote the chats, the keys and the rules, so 20 of 20 meant nothing. On chats written blind, the rules fully got 13 of 29 right and the AI reader 17.
- **WhatsApp limits shape the design.** The official Groups API has participant limits and needs a verified business, so the prototype uses the official webhook format and imports chats from a text export.
- **A model should read, not decide.** The AI reader only reports what it found; code rejects invented prices and a person approves every change.

## Future improvements

| Phase | What |
| --- | --- |
| Now | Prototype: webhook, rules and AI reader, approvals, quote versions, suggestions. Next: score on chats written by teammates, and time the final bill by hand against SMErgers |
| Pilot | 3 to 5 event companies on the official WhatsApp API with consent; Orbyte approvals and eSign; a model trained on real approvals |
| Grow | Renovation, agencies and print; vendor quote comparison; turning a client's photo into a change |

## Contributing

- Commit in small steps with a clear message; each feature comes with tests.
- Run `python -m pytest` before pushing; all tests must pass.
- Use synthetic data only, and never commit secrets or a real `.env`.
- Keep the approval rules on the server: a hidden button is not a permission check.
- Record every accuracy run in [docs/results.md](docs/results.md), including bad ones, and never tune on the blind chats.

## Team

- Vincent Chew Wen Jie ([@Anonys-sky](https://github.com/Anonys-sky))
- Steven Elnathan Meliala ([@stevenmeliala](https://github.com/stevenmeliala))
- Looi Wan Wei ([@wan-wei-looi](https://github.com/wan-wei-looi))

## Submission documents

The proposal, Technical Tools Declaration and proofs of use are in [submission/](submission/README.md).

## License and acknowledgements

Licensed under the [Apache License 2.0](LICENSE).

**Built with Llama.** The AI reader uses Meta Llama 3.1 8B Instruct under the Llama 3.1 Community License. Llama 3.1 is licensed under the Llama 3.1 Community License, Copyright © Meta Platforms, Inc. All Rights Reserved.

Third-party software: Flask, Jinja2, MarkupSafe and Werkzeug (BSD-3-Clause), tzdata (Apache-2.0), pytest (MIT), vLLM (Apache-2.0), Ollama (MIT), and, for the optional bridge only, whatsapp-web.js (Apache-2.0) and qrcode (MIT). Full list with versions: `requirements.txt`, `package.json` and the Technical Tools Declaration.
