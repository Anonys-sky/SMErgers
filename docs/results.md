# Extractor results log

Every run that is quoted anywhere (proposal, deck, video) must appear here, including bad ones.

## Run 1: 22 Oct 2026, rules extractor, commit 9066206

Scored with `python src/evaluate.py` and `python src/evaluate.py --held-out`. A change counts as "fully right" when its status and price both match the hand-written answer key.

| Chats | Changes in keys | Rules: fully right | Naive baseline: fully right | Rules: false changes |
|---|---|---|---|---|
| Tuning (dinner) | 10 | 10 | 3 | 0 |
| "Held-out" (launch, wedding, renovation) | 20 | 20 | 5 | 0 |

Naive baseline: every message containing an RM amount is treated as a change at that amount.

**Caveat, do not quote the held-out number as accuracy.** The same person wrote the held-out chats, their answer keys and the rules, and knew the chats' phrasing while writing the rules. This is contamination, so 20 of 20 shows only that the rules handle the phrasing they were written for. It is not evidence of accuracy on real chats.

**What is needed for an honest number:** new chats written by someone who has not seen the rules (a team member, from memory of real event chats, synthetic names only), with answer keys written before the extractor is run on them. Freeze the rules first, run once, and log the result here as Run 2, whatever it is.

## Run 2: 23 Oct 2026, rules extractor on blind chats, commit 89eaefa

Scored once with `python src/evaluate.py --blind`, after the chats and answer keys were committed and with the rules frozen. Nothing was changed after seeing the result.

**Who wrote the data:** three separate AI agents, each told not to open `src/` and to write the answer key before anything was run. They never saw the extractor. This is independent of the rules' author, but it is still synthetic and still not a human teammate's chat; treat the number as a first independent check, not as accuracy on real chats. Chats written by teammates (kit in `data/blind/`) would be stronger evidence.

| Chat | Changes in key | Found | Fully right (status and price) | False changes |
|---|---|---|---|---|
| Corporate dinner (agent A) | 10 | 8 | 6 | 0 |
| Roadshow launch (agent B) | 10 | 6 | 4 | 1 |
| Chinese wedding (agent C) | 9 | 8 | 3 | 2 |
| **Total** | **29** | **22 (76%)** | **13 (45%)** | **3** |
| Naive baseline (any message with RM) | 29 | 15 | 3 (10%) | 5 |

**Reading it plainly.** On chats the rules were not written for, they fully get 13 of 29 changes right, against 20 of 20 on the chats they were built around. The gap is the contamination in Run 1. The rules still beat the naive baseline (13 against 3), and every miss goes to a person, but they are weak on: a quantity written in words, a price quoted in one message and withdrawn in another, two items in one message, a discount request, and a change agreed with no price anywhere. These are the cases a language model is meant to read better, which is why the chat-reading step is where an AI reader is added (`src/llm_extractor.py`).
