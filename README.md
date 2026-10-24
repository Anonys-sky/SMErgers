# SMErgers

> Changes agreed in a job's WhatsApp group become approved, traceable changes, a new quote version for everyone, and a correct draft final bill. Built for small event companies first, and for any business that works job by job.

**Team VBall** · SDC Hackathon 2026 · Domain 2: Orbyte Smart SME Challenge · SDG 8 (targets 8.2 and 8.3) · [Apache License 2.0](LICENSE)

**Live demo:** [sm-ergers-1.replit.app](https://sm-ergers-1.replit.app) · **Demo video:** (template) · [Slide deck](https://canva.link/yh0xo39bpzxaomf) · [Source code](https://github.com/Anonys-sky/SMErgers)

All data in this repository is synthetic. No real chat, person, client or company is used.

---

## The problem, in one example

A client types in the job's WhatsApp group: *"The LED wall abit small la. Can we upgrade?"* The project manager checks with the vendor. The next morning: *"RM1,100 more."* The client replies: *"ok go ahead."* The quote was signed weeks ago, so that RM1,100 lives only in a chat.

Multiply it by every change on an event: 15 more guests, an hour of overtime, two emergency microphones. In our example job, RM3,860 of changes (11.2% of the RM34,530 quote) were agreed in chat and recorded nowhere. At the end, someone scrolls weeks of messages to rebuild the bill, extras go unbilled, and when the client says "I never agreed to that" there is nothing to show, so the owner often gives the money away. The problem comes from a team member's experience at an event company, where it happened on almost every event; it is one person's account, not a survey.

## What SMErgers does

- **Catch it.** It reads the job's WhatsApp chat and finds each change: what, how many, what price, and whether both sides agreed.
- **Confirm it.** The project manager checks each change, the project director signs off on large or unusual items, and the client confirms or disputes on their own phone-sized page.
- **Sync it.** Every confirmation creates a new quote version (v2, v3 and so on) and posts a summary back to the group. Only confirmed changes reach the draft bill, and every line links to the messages it came from.

When something is unclear it does not guess: a change with no price is marked "needs a price", a discount goes to the project director, and a request nobody agreed to stays unconfirmed.

## Screenshots

<img src="docs/img/review.png" width="760" alt="Project manager review: RM3,540 agreed on top of the RM34,530 quote, the chat with the dinner package messages highlighted, and the changes with Mark checked buttons">

*The project manager checks each change against the highlighted chat messages it came from.*

<img src="docs/img/client-confirmation.png" width="300" alt="The client's phone-sized confirmation page with the source messages and Confirm and Dispute buttons">

*The client confirms or disputes each change from a link, with no login.*

<img src="docs/img/draft-bill.png" width="760" alt="Draft final bill: quote total plus RM3,860 of confirmed changes, with each changed line linked to its source">

*The draft final bill: only confirmed changes, every changed line linked to its chat evidence. A draft, never an invoice.*

## Contents

| Section | What it covers |
| --- | --- |
| [Team information](#team-information) · [Links](#links) | Team, domain, SDG track, all project links |
| [Key features](#key-features) | What the prototype does |
| [How it meets the brief](#how-it-meets-the-brief) | The Domain 2 journey and the six must-haves |
| [Quick start](#quick-start) · [Demo walkthrough](#demo-walkthrough) | Run it and take the three-minute tour |
| [Where AI fits](#where-ai-fits) | Rules reader, AI reader, and the guards around the model |
| [Configuration](#configuration) · [API and webhook](#api-and-webhook) | Environment variables and endpoints |
| [Tech stack](#tech-stack) · [Project structure and architecture](#project-structure-and-architecture) | Technologies, folders and data flow |
| [Testing and results](#testing-and-results) | Tests and measured accuracy |
| [How we use Replit](#how-we-use-replit) · [How we use RunPod](#how-we-use-runpod) | Hosting and GPU use, with proof of use |
| [Business model](#business-model) · [Privacy, boundaries and limits](#privacy-boundaries-and-limits) | Who pays, PDPA, what it does not do |
| [Challenges and learnings](#challenges-and-learnings) · [Future improvements](#future-improvements) | What we learned and what is next |
| [Contributing](#contributing) · [Team](#team) · [Submission documents](#submission-documents) · [License](#license-and-acknowledgements) | The rest |

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
| GitHub Repository | https://github.com/Anonys-sky/SMErgers |
| Live Demo | https://sm-ergers-1.replit.app |
| RunPod Endpoint | https://api.runpod.ai/v2/2y90x5ojwpgxnh (Serverless vLLM, needs an API key kept in Replit Secrets) |
| Slide Deck | https://canva.link/yh0xo39bpzxaomf |
| Demo Video | (template) |

---

## Key features

| Feature | What it does |
| --- | --- |
| Change finder | Finds each change in a chat: follow-ups ("and 1 at the lift lobby also"), recaps, withdrawn requests, "let me ask boss first", Malay and Chinese phrasing, per-unit prices and running totals |
| Evidence beside every change | Every change and bill line highlights the exact messages it came from; one click jumps between them |
| Approvals enforced on the server | The director signs off at RM500 or more, on discounts, on unconfirmed items and on prices typed by staff; a client link cannot approve its own change |
| Role workspaces | Project manager, project director, client and finance views, each with its own queue, filters and checklist |
| Client confirmation page | A phone-sized page opened from a WhatsApp link: confirm, or dispute with a reason; a disputed change stays off the bill |
| Quote versions | Each confirmation makes a new version and queues a summary for the group and the next approver |
| Draft final bill and CSV | Quote plus confirmed changes, what is not on the bill yet and why; a draft for accounting software, never an invoice |
| Tamper-evident activity log | Who did what, in which role, and when; each entry is chained to the one before, so an edit shows |
| Guided journey | A five-step guide on every job says who acts next and hands over in one click |
| "Quote it upfront" suggestions | Counts from past jobs show what usually changes late and what to put in the quote |
| Add project | Create a project with its own quote and chat ([guide](docs/add-a-project.md)) |
| Job API and webhook | A read-only job API and Meta's Cloud API webhook format ([reference](#api-and-webhook)) |

## How it meets the brief

**The five-step journey** required by Domain 2:

| Step | In SMErgers |
| --- | --- |
| Trigger | A message arrives in the job's WhatsApp group (webhook), or a chat export is imported in the prototype |
| Connected data | The signed quote, rate card, client, job and company directory |
| Decision logic | Rules, or an AI reader for messy chats, find each change, its quantity and price, and whether both sides agreed |
| Human approval | PM checks; project director signs off on large or unusual items; client confirms |
| Visible outcome | Quote v2 posted to the group, the draft bill and CSV, and the activity log |

**The six must-have features:**

| Must-have | Where to see it |
| --- | --- |
| One clear SME problem | Agreed changes in WhatsApp never reach the final bill ([problem](#the-problem-in-one-example)) |
| Core automated journey | The five steps above, running in the [demo](#demo-walkthrough) |
| Accuracy and ease of learning | Evidence beside every change, a five-step guide, and measured scores ([results](#testing-and-results)) |
| People stay in control | Role checks on the server and the hash-chained log (`src/workflow.py`, `tests/`) |
| Orbyte fit and reuse | It reuses Orbyte's roles, approvals, eSign and audit trail and adds chat-to-approved-changes. The same engine runs a café renovation chat with only a different quote file, and the job API is a building block. Assumptions: [docs/orbyte-integration.md](docs/orbyte-integration.md) |
| Business benefit and SDG | Extras recovered and hours saved; SDG 8.2 and 8.3 ([business model](#business-model)) |

---

## Quick start

Requirements: Python 3.12. Node.js is only needed for the optional WhatsApp bridge and two test files.

**On Replit:** import this repository (**Create Repl → Import from GitHub**) and click **Run**. The `.replit` workflow starts Flask on port 5000 and the WhatsApp bridge on loopback port 3001 using `scripts/start-application.sh`. Add secrets only if you want the AI reader (see [Configuration](#configuration)).

**Locally:**

```bash
git clone https://github.com/Anonys-sky/SMErgers.git
cd SMErgers
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python src/main.py               # then open http://localhost:5000
```

The app opens on the Project manager workspace with four synthetic projects. State is kept in memory, and **Reset demo data** restores the samples.

### WhatsApp bridge on the published VM

Publishing uses `scripts/build-production.sh` to install the Node dependencies and verify that Chromium can actually launch. Nix supplies Chromium with its Linux shared libraries; the bridge prefers that executable over Puppeteer's standalone download. `scripts/start-application.sh` then runs both Flask and the bridge, and shuts both down if either process exits. Only Flask is publicly exposed; the bridge listens on `127.0.0.1:3001`.

After changing these settings, **republish**: restarting the development workspace does not update the published VM. Open `/whatsapp` in the published app and wait for **Ready for pairing**, then scan the QR code. A running bridge is not the same as a paired account. Linked sessions are not copied from the workspace into a deployment; a new or replaced runtime may need pairing again.

**Access warning:** demo role selection is not authentication. Make the deployment private to invited collaborators before pairing an account. Anyone who can access the app can switch demo roles and use the WhatsApp pages. This remains an unofficial test connector; use synthetic test groups, not real client conversations.

For local development with both services, install the Node dependencies (`npm ci`) and use `npm start`. You can override the browser executable with `PUPPETEER_EXECUTABLE_PATH`; without a system browser the bridge uses Puppeteer's default browser.

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
| `WHATSAPP_BRIDGE_URL`, `WHATSAPP_TIMEZONE` | Optional test bridge (unofficial, not part of the product) | `http://127.0.0.1:3001`, system zone |

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

The group id is read from a `group_id` field on each message, which is our assumption because we had no API access; check it against Meta's Groups API documentation before going live. Messages are delivered to the job linked to that group; the default demo has no linked group, so chats come in by text export. The signature check and the handshake are covered by tests. Limits of the official Groups API: at most 8 participants per group, and an Official Business Account is required. The optional bridge starts alongside the app with the configured launcher (`npm start`), including on the published VM; visit `/whatsapp` to pair it. It uses an unofficial client for team testing only and is not part of the product.

---

## Tech stack

| Layer | Technology |
| --- | --- |
| Web app | Python 3.12, Flask, server-rendered Jinja templates, one CSS file |
| Logic | Rules engine, AI reader, approval workflow, quote versioning, suggestions (Python) |
| Data | In-memory store for the prototype; synthetic JSON data |
| AI / compute | Llama 3.1 8B Instruct on a RunPod Serverless vLLM endpoint (GPU); local Ollama for development |
| WhatsApp | Meta Cloud API webhook format; optional Node.js bridge for team testing only |
| Tests | pytest (290+ tests); Node test runner for the bridge and workspace filters |
| Design, testing and hosting | Replit (workspace, preview, Deployments) |

## Project structure and architecture

```
.
├── src/                 Flask app and logic (main.py, reader.py, rules_extractor.py, llm_extractor.py,
│                        workflow.py, sync.py, bill.py, suggest.py, webhook.py, ...), templates/, static/
├── data/                Synthetic quotes, chats, answer keys, past jobs, company directory (data/README.md)
├── tests/               pytest suite
├── docs/                results.md (every accuracy run), orbyte-integration.md, add-a-project.md, img/
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

Replit is where the team designs, tests and deploys SMErgers.

- **Design:** the interface is built and iterated in the Replit workspace, with the live preview beside the code. Replit Agent helped with configuration and styling, declared in the Technical Tools Declaration.
- **Test:** the app runs in Replit's preview, and the test suite runs in its shell (`python -m pytest`); `requirements.txt` pins the dependencies so Replit matches the local build.
- **Deploy:** the prototype is published with Replit Deployments; `.replit` starts `python src/main.py` on port 5000. Secrets such as `SECRET_KEY` and the AI reader's RunPod keys are set in Replit Secrets and never committed.
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
