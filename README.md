# SMErgers

> Turns changes agreed in WhatsApp into approved changes and a correct draft final bill, for small event companies and other businesses that work job by job.

---

## Team Information

| Field                  | Details |
| ---------------------- | ------- |
| **Team Name**          | VBall |
| **Team Domain**        | Domain 2: Orbyte Smart SME Challenge |
| **SDG Track (1–17)**   | SDG 8 (Decent Work and Economic Growth), targets 8.2 and 8.3 |
| **Team Leader**        | Vincent Chew Wen Jie |
| **University**         | *To fill* |
| **Number of Members**  | 3 |

## Links

| Resource          | Link |
| ----------------- | ---- |
| GitHub Repository | https://github.com/Anonys-sky/SMErgers |
| Replit Project    | *To add after import* |
| Live Demo         | *To add after deployment* |
| RunPod Endpoint   | Not used (no GPU work, see below) |
| Slide Deck        | *To add* |
| Demo Video        | *To add* |

---

## Overview

### Problem

In a small event company, the quote is signed early, then the job changes in the WhatsApp group: 15 more guests, a bigger LED wall, the emcee staying an extra hour. Nobody turns those messages into a record. At the end of the job someone rebuilds the final bill from memory and the chat scroll, extras go unbilled, and when the client says "I never agreed to that", nobody can prove it, so the owner often gives the money away.

This comes from a team member's experience working in an event company, where it happened on almost every event. It is one person's account, not a survey.

### Solution

SMErgers reads the job's WhatsApp group as messages arrive (no export needed), finds each change that was agreed, prices it from the chat, the quote or the rate card, and sends it through the right people: the project manager checks it, the owner signs off on large or unusual items, and the client confirms it on their own page. Each confirmation makes a new version of the quote and posts a summary back to the group, so everyone works from the same numbers. Only confirmed changes reach the draft bill, and every line links back to the exact messages it came from.

**How WhatsApp is read.** The design uses Meta's official WhatsApp Business (Cloud) API: the business number creates one group per job and receives its messages by webhook. The prototype implements that webhook (`POST /webhooks/whatsapp`, Meta's payload format, signature check, verification handshake) and feeds it a synthetic chat one message at a time ("Next message" on the live demo job). Known limits of the official Groups API: up to 8 participants per group and an Official Business Account is required. An optional local connector built on whatsapp-web.js (`whatsapp/bridge.js`) can read an existing group for team testing only: it is an unofficial client, against WhatsApp's terms for production use, so it is not part of the product. Chat exports (.txt) still work as a fallback.

Decisions are made by fixed, explainable rules. When something is unclear, SMErgers does not guess: it marks the change "needs a price" or "needs the owner's decision" and hands it to a person.

### Key Features

- **Change finder:** groups messages into threads and works out what changed, by how much, at what price, and whether both sides agreed. Handles follow-ups ("and 1 at the lift lobby also"), recaps, withdrawn requests and "let me ask boss first".
- **Show in chat:** every change and bill line highlights the messages it came from, which settles disputes in seconds.
- **Approval by the right role:** PM checks, owner signs off at RM500 or more (and on discounts, unconfirmed items and staff-entered prices), client confirms or disputes with a reason. Enforced on the server, not only hidden in the page.
- **Live from WhatsApp:** messages arrive through the webhook; new changes appear as people talk, and the PM is told straight away.
- **Everyone in sync:** the next person is messaged when a change needs them (owner approval, client confirmation); each client confirmation makes quote version 2, 3… and posts a summary back to the group.
- **Next time, quote it upfront:** counts from past jobs show what usually changes late in this kind of event (e.g. "the event ran past the planned end in 4 of 4 dinners") and the one step that moves that decision into the quote. Plain counting over a simulated job history, so every line can be checked by hand; a trained model can replace it once real, human-approved history exists.
- **Named approvers:** people come from a company directory (Orbyte's Directory, simulated in `data/team.json`).
- **Draft final bill:** the quote with adjusted quantities plus agreed changes, what is not on the bill yet and why, and a CSV export for accounting software.
- **Activity log:** who did what and when, each entry chained to the one before so later edits show.

### Where AI fits

The current version uses **no AI model**: rules handle the extraction and every decision, because a reason an owner can read matters more than a score. A language model may later read phrasing the rules have never seen, but only if it beats the rules on chats the rules were not written for (see [Results](#results)). No model is trained, so no GPU is needed.

### Tech Stack

| Layer         | Technology |
| ------------- | ---------- |
| Frontend      | Server-rendered HTML (Jinja templates), one CSS file, a few lines of JavaScript for highlighting |
| Backend       | Python 3.12, Flask |
| Database      | In-memory store for the prototype (demo data resets on restart) |
| AI / Compute  | None in this version |
| Hosting / Dev | Replit |

---

## Project Structure

```
.
├── data/                    # Synthetic data only (see data/README.md)
│   ├── quotes/              # Signed quote + rate card per job
│   ├── chats/               # WhatsApp-style exports
│   ├── answer_keys/         # Hand-written expected changes, for scoring
│   └── vendor_invoices/     # Synthetic vendor invoice (for a later vendor check)
├── docs/
│   ├── results.md           # Every accuracy run, including caveats
│   └── orbyte-integration.md
├── src/
│   ├── main.py              # Web app entry point (routes only)
│   ├── chat_import.py       # WhatsApp export parser
│   ├── catalogue.py         # Quote lines and rate card, and the words that name them
│   ├── rules_extractor.py   # Finds the changes agreed in a chat
│   ├── workflow.py          # Approval flow, permissions, activity log
│   ├── bill.py              # Matches confirmed changes to the quote, builds the draft bill
│   ├── evaluate.py          # Scores the extractor against the answer keys
│   ├── schema.py            # Shared data shapes
│   ├── store.py             # In-memory jobs, demo reset, live demo feed
│   ├── webhook.py           # WhatsApp Cloud API webhook format, signature check, live ingestion
│   ├── sync.py              # Quote versions and messages back to the group or the next approver
│   ├── whatsapp_bridge.py   # Optional local connector to whatsapp/bridge.js (team testing only)
│   ├── templates/  static/
├── submission/              # Required submission documents (see submission/README.md)
├── tests/                   # pytest
├── .env.example  .gitignore  .gitattributes  .replit  LICENSE  requirements.txt  README.md
```

### Architecture

```
WhatsApp group ──webhook──► webhook.py ──► rules_extractor ──► workflow (PM ► owner ► client) ──► bill ──► CSV
(or .txt export ──► chat_import)              ▲                       │                              │
                                quote + rate card (catalogue)   sync.py: quote v2, v3…        GET /api/jobs/<id>
                                                                messages back to the group
                                                                and the next approver
                                                                activity log
```

---

## How to Run

### Option 1: Run on Replit

1. Import this repository: **Create Repl → Import from GitHub**.
2. Optional: in **Secrets**, add `SECRET_KEY` (see `.env.example`).
3. Click **Run**. Replit uses `.replit` to start `python src/main.py`.

### Option 2: Run locally

```bash
git clone https://github.com/Anonys-sky/SMErgers.git
cd SMErgers
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python src/main.py               # then open http://localhost:8080
```

### Run tests and accuracy scores

```bash
python -m pytest
python src/evaluate.py
```

### Demo walkthrough (about 3 minutes)

1. Open the live job (**Start with the demo** on the home page). Press **Next message** a few times: messages arrive from the WhatsApp group and changes appear as people talk. Then **Play the rest**.
2. Click **Show in chat** on the LED wall upgrade: the request, the price and the "ok go ahead" light up.
3. The wireless mics have no price anywhere, so they are marked **Needs a price**. Set RM320; the owner must now approve it, because staff entered the price.
4. As **Project manager**, check the changes. As **Owner**, approve the ones over RM500.
5. As **Client**, confirm the changes, and dispute the banners ("we asked for 2"). Switch back and click **Show in chat**: the client's own "2 more" and "and 1 at the lift lobby" settle it.
6. Back in the chat, SMErgers has posted "quote version 2" to the group. Open **Quote versions and messages**, **Draft bill** and **Activity log**.

---

## How We Use Replit *(Required)*

- **Hosting:** *to complete after deployment: Replit Deployments at the Live Demo link above.*
- **Development:** *to complete: describe how the team used the Repl.*
- **Secrets:** `SECRET_KEY` is kept in Replit Secrets, never in the code.

Proof of use: `submission/REPLIT PROOF OF USE.pdf` *(to add)*

## How We Use RunPod

Not used. The handbook (section 9.4) requires RunPod for work that needs a GPU: training, fine-tuning or running a model on a GPU. SMErgers runs no model, so it needs no GPU.

---

## Results

Scored with `python src/evaluate.py` against hand-written answer keys. Full log, with caveats: [docs/results.md](docs/results.md).

| Chats | Changes | Rules: fully right | Baseline (any message with an RM amount): fully right |
|---|---|---|---|
| Tuning (dinner) | 10 | 10 | 3 |
| Other three chats | 20 | 20 | 5 |

**These are not accuracy figures.** The same person wrote the chats, the answer keys and the rules. An honest score needs new chats written by someone who has not seen the rules, run once.

## Privacy and boundaries

- **Synthetic data only.** No real chat, person, client or company is used.
- **No payments, filings or advice.** The bill is a draft for accounting software; nothing is sent or paid. The record of what was agreed is not legal proof or legal advice.
- **PDPA in a real deployment:** chat exports contain personal data of clients and vendors, so the company would tell them chats are used to record agreed changes, keep only the messages linked to changes and delete the rest after import, limit access by role, set a retention period, and let people ask for their data. A real pilot needs a legal review first.

## Known limits

- Rules only understand phrasing they were written for; unseen slang, typos and voice notes will be missed.
- Dates are read day-first, as WhatsApp exports them in Malaysia.
- Data is held in memory; a restart resets the demo.
- Sign-in and roles are simulated.

## Future Improvements

- [ ] Score on chats written by someone who has not seen the rules, then decide whether a language model is worth adding.
- [ ] Vendor check: the vendor's invoice against what was agreed with them (synthetic data is in `data/vendor_invoices/`).
- [ ] Connect to Orbyte projects, approvals, eSign and audit trail ([docs/orbyte-integration.md](docs/orbyte-integration.md)).

## Team

| Name | Role | GitHub |
| ---- | ---- | ------ |
| Vincent Chew Wen Jie | Team leader | [@Anonys-sky](https://github.com/Anonys-sky) |
| Looi Wan Wei | *To fill* | *To fill* |
| Steven Elnathan Meliala | *To fill* | *To fill* |

---

## Submission Checklist

- [x] Domain and SDG track filled in
- [x] Team name, leader and members filled in
- [ ] University, member roles and GitHub handles filled in
- [ ] Slide deck link added
- [ ] Demo video link added
- [ ] Replit used, with proof of use in `submission/`
- [x] RunPod: not used (no GPU work), stated above
- [ ] Submission template completed in `submission/`
- [ ] Technical Tools Declaration lists every tool, including AI coding assistants
- [ ] "How to Run" steps verified on Replit
- [x] No API keys or secrets committed
- [ ] Repository public, committee accounts added as collaborators

## License

This project is licensed under the [Apache License 2.0](LICENSE).
