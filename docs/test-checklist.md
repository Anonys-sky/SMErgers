# Test checklist for the second laptop

Run this after the setup in [demo-setup.md](demo-setup.md). Tick each box, and write down anything that differs from "Expected". Send the result sheet at the bottom back to the team. About 30 minutes.

## A. It starts (5 minutes)

- [ ] `python -m pytest -q` ends with **all passed** (on Windows add `--deselect tests/test_startup.py`). Write the count: ____
- [ ] `npm test` ends with 0 failed (one test may be skipped on Windows).
- [ ] http://localhost:5000 opens. **Skip tutorial** works. The overview shows five projects.
- [ ] Open each page without an error: Overview, Projects, Import chat, WhatsApp bridge, Workflow guide.

## B. Live sync (10 minutes)

- [ ] **Pairing:** the badge goes Ready for pairing, then **Connected**.
- [ ] The **Choose the group** form lists your test group.
- [ ] After connecting, the project shows the messages already in the group.
- [ ] Send the scripted messages from [demo-setup.md](demo-setup.md), step 5. After **each** message, the page updates in **under 10 seconds** without you pressing reload. Write the slowest delay: ____ s
- [ ] The final state has exactly **5 changes** with the statuses in the guide.
- [ ] **Activity log** has one "registered through the WhatsApp bridge" line per message, and each change has a "found in chat" line.
- [ ] Reconnecting or restarting the bridge does **not** duplicate any message or change.
- [ ] Send the same sentence twice from the client phone (two separate messages): both are kept (they are different messages).

## C. The six must-haves, live (10 minutes)

1. **One clear problem:** the overview and the project explain it in plain words without help.
   - [ ] A first-time person can say what the product does after 30 seconds.
2. **Core journey end to end** (trigger, data, decision, approval, action, result):
   - [ ] As **Project Manager**: use Show in chat on the LED wall (the request, the price and "ok go ahead" light up), add a price to the Wireless mic, press **Check all**.
   - [ ] As **Project Director**: the money strip shows three numbers; the queue has Approve and Reject on each row.
   - [ ] **Approve** one change. The next step becomes "client confirms".
   - [ ] **Reject** one change **without** a reason: refused. With a reason: it leaves the bill and the PM gets a notice (Activity log, Messages SMErgers sent).
   - [ ] As **Client** (Open the client's link): confirm the approved changes. Quote version 2 is posted in the history.
   - [ ] **Draft bill** shows the quote plus only the confirmed changes. CSV downloads and is marked DRAFT.
3. **Accuracy and repeatable:**
   - [ ] Press **Reset demo data**, reconnect, resend the script. The **same five changes** appear again.
   - [ ] First-time use: someone who has not seen it follows the guide steps on the job page without being told what to click.
4. **People stay in control:**
   - [ ] As **Client**: no Approve button, and `http://localhost:5000/api/jobs` is refused.
   - [ ] As **Finance**: the bill is visible, and there are no approval actions.
   - [ ] A change worth **RM500 or more** needs the director; the PM cannot approve it.
   - [ ] The **Activity log** lists exactly what you just did, in order, with who and when. The line "Integrity check passed" is shown.
5. **Orbyte fit and a second business:**
   - [ ] Open the **Cafe fit-out** project: its sign-off limit is **RM2,000** (the director overview lists every business's limit).
   - [ ] **Add project** opens a form where a new business enters its own quote lines and limit.
   - [ ] `http://localhost:5000/api/jobs` (as PM) lists every job; `/api/jobs/annual-dinner` returns the changes, bill and log.
6. **Benefit in numbers:**
   - [ ] `python src/benefit.py --split blind` prints a table that ends "Of 11 agreed, billable changes ... 11 reached the bill".

## D. Things judges might type (5 minutes)

Send each from the **client phone**, then answer from the staff phone where noted. Write what the app shows.

| Typed | Expected | Seen |
|---|---|---|
| Please add 10 more guests | Dinner package, +10, RM1,280, unconfirmed | |
| (staff) ok noted | that change becomes ready | |
| We need 2 extra microphones, RM80 each | Microphones, RM160, unconfirmed | |
| Can we upgrade the stage? let me ask my boss first | Stage, unconfirmed, no price | |
| Please cancel the balloon arch | a Balloon arch entry (check it is not marked ready) | |
| Can you do 15% discount? | needs the director | |

A **duplicate entry** for the same request is a known quirk of the rules reader: the PM rejects one with a reason, or adds the missing one with "The reader missed something?".

## E. When things fail (5 minutes)

- [ ] Stop the bridge (close its terminal). The WhatsApp page says **Bridge not running**; with `npm start` and `SMERGERS_KEEP_APP_UP=1` the rest of the app keeps working.
- [ ] **Import chat** with `data/chats/dinner_client.txt` and the Annual Dinner quote works as the fallback.
- [ ] Tick **Read with the AI reader** on the import with RunPod off: after at most 60 seconds the page says the AI could not be reached and the rules read it.
- [ ] Restart the app: demo data resets (this is expected).

## Result sheet (send this back)

- Laptop and system: ____________   Python: ____   Node: ____   Browser: ____
- Pytest count: ____ passed, ____ failed.   Bridge npm test: ____
- Slowest message delay: ____ s.   Final change count after the script: ____ (expected 5)
- Failed boxes (copy the letter and the line): ____________
- Anything confusing for a first-time user: ____________
- Screenshots of any error page or the Activity log: attach.
