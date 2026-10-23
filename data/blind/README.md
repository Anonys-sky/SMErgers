# Blind test: write chats the rules have never seen

Why: our first accuracy scores are not independent, because one person wrote the chats, the answer keys and the rules. The only honest number comes from chats written by someone who has **not** seen the rules. That is you.

All names, companies and numbers must be invented. Never paste a real chat.

## The one rule

**Do not open `src/rules_extractor.py` or `src/evaluate.py` and do not run the app on your chat until your chat and your answer key are committed.** We run the scorer once, afterwards, and report the result whatever it is. A bad score is useful: it shows what to fix and what the pilot must test.

## What to write (about 30 to 60 minutes each)

1. **A chat**, 25 to 45 messages, as WhatsApp would export it. Copy the format from `data/chats/dinner_client.txt`:
   `15/09/2026, 2:05 pm - Linda (Client): text`
   Write it the way event chats really read: Manglish, short replies ("ok", "can", "noted"), typos, people changing their minds, "let me ask boss first", a price said by one person and agreed by another a day later, a request that is never confirmed, a discount, an extra with no price, a recap message, a photo or voice note ("<Media omitted>").
2. **A quote** the chat belongs to, with 6 to 10 lines, using `quote_template.json`. Use your own words for the items, as a real company would. Give each line a few `aliases`: other words people use for it in chat.
3. **An answer key**: the changes a careful person would find, using `key_template.json`. Write it **before** anything is run.

## Where the files go (commit from your own GitHub account)

| File | Path |
|---|---|
| Chat | `data/chats/blind_<yourname>.txt` |
| Quote | `data/quotes/q_blind_<yourname>.json` |
| Answer key | `data/answer_keys/blind_<yourname>.json` (set `"split": "blind"`) |

Commit the three files in separate small commits, for example "data: blind chat by Looi", "data: blind quote", "data: blind answer key". Your commits count as your contribution.

## Answer key, in plain words

For each change write:
- `key`: a short name, e.g. `extra_banners`.
- `kind`: `quantity_change`, `upgrade`, `replacement`, `extra`, `discount` or `non_billable`.
- `line_id`: the quote line it changes (`L03`), or `null` for an extra that is not on the quote.
- `qty_delta`: how many more or fewer (`+3`, `-2`), or 0.
- `price_delta`: the money change in RM, or `null` if nobody ever said a price.
- `status`:
  - `ready`: both sides agreed and a price is known;
  - `needs_price`: agreed, but no price anywhere;
  - `needs_decision`: a discount with no clear amount, for the owner to decide;
  - `unconfirmed`: asked or priced, but never agreed;
  - `withdrawn`: raised, then taken back;
  - `log_only`: agreed at no extra cost.
- `evidence`: short phrases copied **exactly** from the messages that prove it. These are checked automatically.

Also set `expected_known_delta` to the sum of `price_delta` of all `ready` changes.

## Check your own files (this does not run the rules)

```bash
python -m pytest tests/test_data.py
```

It checks that every evidence phrase appears in your chat, that line ids exist in your quote, and that the delta adds up. Fix anything it reports.

## What happens next

Run 2 and Run 3 in `docs/results.md` already score three chats written by independent AI agents. Teammates' chats added here would be scored as a further run, reported whatever it is, next to the baseline. We then use that number, honestly, in the proposal and the pitch.
