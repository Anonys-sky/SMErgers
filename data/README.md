# Synthetic data

Everything in this folder is invented by the team. No real chat, person, client or company is used. Names, phone numbers and email domains are fictional (`.example`).

- `quotes/`: the original signed quote for each job, plus a rate card for common extras.
- `chats/`: WhatsApp-style group exports (Android export format). Written from team experience of how event chats read, not copied from any real chat.
- `answer_keys/`: the changes a careful person would find in each chat. Used to measure the extractor. Written by hand before the extractor was run on that chat.
- `vendor_invoices/`: synthetic vendor invoices and the vendor's original quote, for the vendor check.

Split: `dinner_client` was used to build the rules. The launch, wedding and renovation chats were meant to be held out, but the rule writer knew their phrasing, so they no longer count as an independent test (see `docs/results.md`). The three `blind_agent_*` chats, quotes and answer keys were written by separate AI agents that never saw the extractor and were committed before any scoring (`docs/results.md`, Runs 2 and 3). They are synthetic. Chats written by teammates (kit in `blind/`) would be stronger evidence and are still welcome.
