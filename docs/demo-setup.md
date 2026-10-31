# Demo setup: run SMErgers on a laptop with a real WhatsApp group

For the live demo and for testing on another laptop. About 20 minutes the first time. Synthetic data only: use **spare test numbers**, never a customer's.

## What you need

| Item | Notes |
|---|---|
| Python 3.12 | `python --version` |
| Node.js 22.12 or newer | `node --version` |
| Google Chrome or Chromium | the bridge uses it to run WhatsApp Web |
| **Two phones with two different numbers** | Phone A = the **staff** phone, linked to the bridge. Phone B = the **client** phone, only a member of the group. |
| Internet | WhatsApp Web needs it. The rules reader does not. |

**Why two phones.** The reader only counts a "yes" that comes from a different sender than whoever asked (`tests/test_demo_script.py` checks this). One phone typing both sides leaves every change unconfirmed.

**Do not** let a judge or anyone else type from their own phone: their number would enter the app, and the competition requires synthetic data only. A team member types on the client phone for them.

## 1. Install (once)

```bash
git clone https://github.com/Anonys-sky/SMErgers.git
cd SMErgers
python -m venv .venv
# Windows (PowerShell):  .venv\Scripts\Activate.ps1      Mac or Linux:  source .venv/bin/activate
pip install -r requirements.txt
npm ci
npm run check:browser        # should print "Browser check passed"
python -m pytest -q          # on Windows add:  --deselect tests/test_startup.py
```

## 2. Start

**Mac, Linux, or Windows with Git Bash:** one command starts the app and the bridge together.

```bash
npm start
```

**Windows without bash:** two terminals, from the repo folder (with the virtual environment active in the first).

```bash
python src/main.py
```
```bash
npm run whatsapp
```

Open http://localhost:5000. On a Mac where AirPlay holds port 5000, run `PORT=5001 npm start` and open port 5001.

Optional settings (environment variables, never in the repo):
- `SMERGERS_KEEP_APP_UP=1` keeps the app serving if only the bridge stops (with `npm start`).
- `RUNPOD_ENDPOINT_ID` and `RUNPOD_API_KEY` switch on the AI reader on RunPod. Leave them unset for the demo: the rules reader is instant and repeatable. If you do tick **Read with the AI reader** on a group, the rules still answer at once and the AI refines in the background (it needs RunPod warmed up first; otherwise the rules answer stays and the activity log says the AI could not be reached).

Click **Skip tutorial** once (it opens on every first visit).

## 3. Pair the staff phone

1. Open **WhatsApp bridge** in the left menu. The badge should say **Ready for pairing**.
2. On **phone A**: WhatsApp, Linked devices, Link a device, scan the QR code (or use "Link with phone number instead" and type the 8-character code).
3. Wait for the badge to say **Connected**.

## 4. Make the group and connect it

1. On phone A, create a WhatsApp group named for example "Annual Dinner demo". Add **phone B**.
2. In the app, switch the demo role to **Project Manager** and press **Reset demo data** (the project must be unreviewed to connect).
3. Open **WhatsApp bridge**. Once the badge says Connected, a **Choose the group** form appears. Pick the group, pick the project **Annual Dinner 2026**, leave **Read with the AI reader** unticked, and press **Connect group and find changes**.

## 5. Send the scripted conversation (before the pitch)

The messages are in `data/demo_group_script.json`. Send them **in order**, each from the phone listed (staff = phone A, client = phone B). Wait about 5 seconds between messages and watch the project page update.

| # | From | Message | What appears |
|---|---|---|---|
| 1 | staff | Hi Mr Tan. Attaching the signed quote Q-2026-041 for the Annual Dinner on 10 Oct, 180 pax. | nothing yet |
| 2 | client | Hi, our HR confirmed 195 people attending. Quote was 180 right? Can adjust to 195? | Dinner package, 15 more, RM1,920, unconfirmed |
| 3 | staff | Noted, I update to 195 pax. Will reflect in the final bill ya | Dinner package is now ready |
| 4 | client | The LED wall abit small la. Can we upgrade to 4m x 2.5m? | LED wall upgrade, no price, unconfirmed |
| 5 | staff | Let me check with the vendor and revert | no change |
| 6 | staff | LED upgrade will be RM 1,100 more Mr Tan | LED wall priced RM1,100, unconfirmed |
| 7 | client | ok go ahead | LED wall is now ready |
| 8 | client | I want 2 more roll-up banner at the entrance | Roll-up banner, 2 more, RM180, unconfirmed |
| 9 | staff | ok can, 2 more banners noted | Roll-up banner is now ready |
| 10 | client | Can we get a 10% discount ah? | Discount 10%, goes to the director |

During the pitch (the "on the spot" moment), send from the client phone: **"Emergency! need 2 extra wireless mic for speeches, quick!!"**, then from the staff phone: **"ok noted, will arrange"**. Result: Wireless mic, 2, needs a price (the PM adds it; the director signs off if it is RM500 or more).

Expected final state: **5 changes**: Dinner package (ready), LED wall (ready), Roll-up banner (ready), Discount 10% (needs the director), Wireless mic (needs a price).

## 6. Run the demo

Follow the run sheet in `Submission Drafts/FINALS_PITCH_SCRIPT.md`. The short version: director overview, a message arrives, Show in chat, Approve, Reject with a reason, client confirms, Activity log, draft bill, café project for the second business.

## If something goes wrong

| Symptom | Fix |
|---|---|
| Badge says **Bridge not running** | Start the bridge (`npm run whatsapp`) or use `npm start`. |
| No QR code | Check internet, run `npm run check:browser`, restart the bridge. |
| Pairing worked, no **Choose the group** form | Wait 20 seconds for WhatsApp Web to finish syncing, then reload the page. |
| A message does not appear within 10 seconds | The page refreshes every 3 seconds. Check the **Activity log** for "registered through the WhatsApp bridge". If missing, the bridge lost its session: re-pair. |
| Everything stays "unconfirmed" | The yes came from the same phone as the request. Use two phones. |
| "Project already connected" | Press **Reset demo data**, then connect again. |
| "AI reader could not be reached" | Expected when RunPod is off. The rules reader read the chat instead. |
| Anything else, 10 minutes before | Use **Import chat** with `data/chats/dinner_client.txt` and the Annual Dinner quote. The rest of the demo is identical. |

After testing, **delete the WhatsApp group and unlink the device** on phone A.
