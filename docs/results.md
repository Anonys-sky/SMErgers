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

## Run 3: 23 Oct 2026, AI reader (llama3.1:8b, local Ollama) on the same blind chats, commit f4fca5e

Scored once with `python src/evaluate.py --blind --ai`, on the same three blind chats as Run 2. The prompt and checks in `src/llm_extractor.py` were tuned on the tuning chat only (dinner_client) before this run, and not changed afterwards. Run on a laptop with an NVIDIA RTX 2050 (4 GB), through a local Ollama server, which put part of the model on the GPU (about 2.3 of 5.6 GB). Handbook section 9.4 requires RunPod for work that needs a GPU, including inference; the AI reader does not require a GPU to run, but this run used one. See submission/README.md. Same caveat as Run 2: the chats were written by independent AI agents, they are synthetic, and 29 changes is a small sample.

| Reader | Found | Fully right (status and price) | False changes |
|---|---|---|---|
| Naive baseline | 15 of 29 | 3 (10%) | 5 |
| Rules (Run 2) | 22 of 29 (76%) | 13 (45%) | 3 |
| **AI reader** | **28 of 29 (97%)** | **18 (62%)** | **1** |

By chat, fully right: A 6 of 10, B 6 of 10, C 6 of 9 for the AI reader, against 6, 4 and 3 for the rules.

**Where the AI reader is better:** quantities in words, a price quoted then withdrawn, two items in one message, discount requests (it sent all three to the owner), and reductions priced from the quote.

**Where it is still wrong, plainly:** it sometimes marks a change "ready" that was never confirmed (centrepieces), calls a "price later" item ready by pricing it from the quote (second lion dance, RM1,200), and files colour or time swaps as "needs a price" instead of "no cost". It over-bills in total on chat C (RM9,940 against RM3,620 expected), which is exactly why nothing is billed without the project manager's check and the client's yes. It takes about 2 minutes per chat on a laptop GPU (RTX 2050), so it is not fast enough for live use on that machine.

**Not claimed:** accuracy on real chats. Next: teammates' chats, a faster hosted or larger model, and a rule that stops "ready" without an explicit yes.

## Run 4: 24 Oct 2026, AI reader on the same blind chats, CPU only, commit de36caf

Same command as Run 3, against a separate local Ollama server started with the GPU disabled (`CUDA_VISIBLE_DEVICES=-1`, Vulkan off); its log reports `inference compute id=cpu`. Prompt and checks unchanged from Run 3.

| Reader | Found | Fully right (status and price) | False changes |
|---|---|---|---|
| AI reader, CPU only | 27 of 29 | 18 (62%) | 1 |

By chat, fully right: A 7 of 10, B 5 of 10, C 6 of 9. The total matches Run 3; individual answers differ slightly because the model's output is not exactly repeatable. Run 5 supersedes this run for quoting. Same caveats: 29 changes, synthetic chats written by AI agents.

## Run 5: 24 Oct 2026, AI reader on RunPod (GPU) on the same blind chats, commit 1173d1e

Same command as Runs 3 and 4 (`python src/evaluate.py --blind --ai`), but the model ran on a RunPod Serverless vLLM endpoint: `meta-llama/Llama-3.1-8B-Instruct`, `MAX_MODEL_LEN` 8192, one RTX 4090 (24 GB) worker, image `runpod/worker-v1-vllm:v2.30.1`, endpoint ID `2y90x5ojwpgxnh`. The endpoint's job counter went up by 3, one per chat, so no chat fell back to the rules. Prompt and checks unchanged from Run 3. This is the run that follows handbook section 9.4 (GPU work on RunPod).

| Reader | Found | Fully right (status and price) | False changes |
|---|---|---|---|
| AI reader, RunPod RTX 4090 | 26 of 29 (90%) | 17 (59%) | 1 |

By chat: A found 10 of 10, 7 fully right, 0 false; B found 7 of 10, 4 fully right, 0 false; C found 9 of 9, 6 fully right, 1 false. Total ready amount against the key: A RM4,344 (RM3,834), B RM1,390 (RM2,590), C RM8,740 (RM3,620).

**Compared with Runs 3 and 4:** one fewer change found than Run 4 (27) and two fewer than Run 3 (28), and one fewer fully right (17 against 18). The model is the same, but the serving stack is different (vLLM instead of Ollama, bf16 instead of a quantised model) and the output is not exactly repeatable, so a gap of one or two changes is not evidence that one setup is better. Same caveats: 29 changes, synthetic chats written by AI agents.

**Where it was wrong:**
- Chat B: missed the discount request, the extra registration counter and the drone operator, and called the venue extension "needs a price". It also filed the tote colour and load-in time as "needs a price" instead of "no cost".
- Chat A: marked the centrepieces "ready" although the client never confirmed, and filed the backdrop colour and arrival time as "needs a price".
- Chat C: the withdrawn peony upgrade came back as "unconfirmed" at RM30, the "price later" second lion dance was priced at RM1,200 (one false change), and the band start time was filed as "needs a price".

**Timing:** the first request waited about 2.5 minutes for the worker to start and load the model (cold start); once warm, a request ran in under a second. Billing for this run had not yet appeared when it was written (it lags by up to an hour).
