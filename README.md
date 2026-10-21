# SMErgers: OnRecord (working name)

SDC Hackathon 2026, Domain 2 (Orbyte Smart SME Challenge: Less Busywork, Better Business).

**Problem.** In small event companies, changes and extras are agreed in WhatsApp chats, but nobody turns them into a record. At job close the final bill is rebuilt from memory, nobody can prove what was agreed, and the owner often gives the money away to keep the client.

**What it does.** Imports a WhatsApp group export, extracts the changes agreed, matches them to the original quote, routes them for approval by the right role, and produces a draft final bill with a record of who agreed what and when. AI only reads the messy text. Fixed rules decide. A person approves.

**Status.** Work in progress. Nothing here is a finished product.

## Boundaries (from the Domain 2 brief)

- No real payments, no statutory filings, no legal or financial advice.
- All data is synthetic and labelled. No real chats, customers or companies are used.
- The output is a *draft* for the owner's accounting software and a record of what was agreed, not legal proof.
- Login, roles, eSign and Orbyte data are simulated.

## Run

```bash
pip install -r requirements.txt
python src/main.py
```

## Tools

- Replit: hosting and deployment (proof of use to be added in `submission/`).
- GitHub: this repository, Apache 2.0.
- RunPod: not used. No GPU workload is needed.
