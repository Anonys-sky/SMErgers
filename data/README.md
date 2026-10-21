# Synthetic data

Everything in this folder is invented by the team. No real chat, person, client or company is used. Names, phone numbers and email domains are fictional (`.example`).

- `quotes/`: the original signed quote for each job, plus a rate card for common extras.
- `chats/`: WhatsApp-style group exports (Android export format). Written from team experience of how event chats read, not copied from any real chat.
- `answer_keys/`: the changes a careful person would find in each chat. Used to measure the extractor. Written by hand before the extractor was run on that chat.
- `vendor_invoices/`: synthetic vendor invoices and the vendor's original quote, for the vendor check.

Split for honest testing: `dinner_client` and `dinner_vendor` are used to build the rules. The other chats are held out and only used to measure.
