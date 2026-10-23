"""Web app. All decisions happen in the engine modules; these routes only call them and render."""
import csv
import io
import os
import re
import secrets

from flask import (Flask, Response, abort, flash, jsonify, redirect, render_template, request, send_from_directory,
                   session, url_for)
from markupsafe import Markup, escape

import store
import suggest
import sync
import webhook
import whatsapp_bridge
from project_intake import InvalidProject, prepare
from chat_import import InvalidChatTimestamp, parse_chat
from navigation import local_return_path
from bill import build_bill
from schema import STATUSES
from workflow import ACTIONS, STATE_LABELS, NotAllowed
from workspaces import PERSONAS, build_workspace

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or os.environ.get("SESSION_SECRET") or secrets.token_hex(16)
app.config["MAX_CONTENT_LENGTH"] = 1_000_000  # chat exports are small text files

store.reset_demo()


@app.get("/favicon.ico")
def favicon():
    return send_from_directory(app.static_folder, "favicon.svg", mimetype="image/svg+xml")


def current_role():
    role = session.get("role", "pm")
    return role if role in store.ROLE_LABELS else "pm"


def get_record(job_id):
    record = store.JOBS.get(job_id)
    if record is None:
        abort(404)
    return record


def selected_client_job():
    """The sample event the client workspace shows: the last client link opened, else the first
    finished sample job. A client reaches a job through its WhatsApp link, so this is a demo
    context, not an authenticated account."""
    chosen = session.get("client_job_id")
    if chosen in store.JOBS:
        return chosen
    return next((job_id for job_id, r in store.JOBS.items() if not r.live), next(iter(store.JOBS), None))


def managers_only():
    if current_role() not in ("pm", "owner"):
        abort(403)


def staff_only(job_id):
    """Clients only ever see their confirmation page, never the team's internal views."""
    if current_role() == "client":
        return redirect(url_for("client_page", job_id=job_id))
    return None


@app.errorhandler(403)
def forbidden(error):
    return render_template(
        "error.html", code=403, heading="Not available in this workspace",
        explanation="Use your role's available actions or switch demo workspaces. This page belongs to another role or sample client.",
    ), 403


@app.errorhandler(404)
def not_found(error):
    return render_template(
        "error.html", code=404, heading="Page not found",
        explanation="This project, change or workspace does not exist. Return to your workspace to choose an available project.",
    ), 404


@app.errorhandler(413)
def too_large(error):
    return render_template(
        "error.html", code=413, heading="Chat export is too large",
        explanation="Choose a WhatsApp text export under 1 MB without media.",
    ), 413


@app.template_filter("rm")
def rm(value):
    if value is None:
        return "No price yet"
    sign = "−" if value < 0 else ""
    return f"{sign}RM{abs(value):,.2f}".replace(".00", "")


# Words in a chat message that carry the deal: money, quantities, yes and no.
DEAL_TERMS = re.compile(
    r"(?:[+-]\s?)?RM\s?[\d,]+(?:\.\d+)?(?:\s*(?:more|less|each|per \w+))?"
    r"|\b\d+\s*(?:more|extra|instead of \d+)\b|\btotal \d+\b|\b\d+ total\b|加多\d+个?|tambah \d+"
    r"|\b(?:ok|okay|go ahead|proceed|fine|noted|no need|cancel|same price|no extra|included)\b",
    re.I,
)


@app.template_filter("marked")
def marked(text):
    """Escape the message first, then highlight the deal terms, so chat text can never inject HTML."""
    return Markup(DEAL_TERMS.sub(lambda m: f"<mark>{m.group(0)}</mark>", str(escape(text))))


@app.context_processor
def shared():
    role = current_role()
    profile = PERSONAS[role]
    return {"role": role, "roles": store.ROLE_LABELS, "state_labels": STATE_LABELS,
            "status_labels": STATUSES, "personas": PERSONAS, "profile": profile,
            "workspace_url": url_for("workspace_page", persona=profile["slug"])}


@app.get("/")
def home():
    return render_workspace()


def render_workspace():
    role = current_role()
    records = list(store.JOBS.values())
    if role == "client":
        records = [record for record in records if record.id == selected_client_job()]
    export_snapshots = session.get("bill_exports", {})
    exported_jobs = {
        record.id for record in records
        if export_snapshots.get(record.id) == record.job.log.entries[-1].hash
    }
    workspace = build_workspace(role, records, needs, exported_jobs=exported_jobs)
    view = request.args.get("view", "overview")
    allowed_views = {"overview", "projects", "tasks", "activity"} - ({"activity"} if role == "client" else set())
    workspace["view"] = view if view in allowed_views else "overview"
    live = next((r for r in store.JOBS.values() if r.live), None) if role in ("pm", "owner") else None
    return render_template(
        "workspace.html", workspace=workspace, allowed=allowed_actions, live=live,
        live_bill=build_bill(live.catalogue, live.job) if live else None,
        selected_client_job=selected_client_job(),
        client_options=[(r.id, r.catalogue.quote["client"], r.title) for r in store.JOBS.values()],
    )


@app.get("/workspace/<persona>")
def workspace_page(persona):
    """Dedicated demo workspaces; selecting one is explicitly not authentication."""
    role = next((key for key, profile in PERSONAS.items() if profile["slug"] == persona), None)
    if role is None:
        abort(404)
    if role == "client" and "job_id" in request.args:
        if request.args["job_id"] not in store.JOBS:
            abort(404)
        session["client_job_id"] = request.args["job_id"]
    session["role"] = role
    return render_workspace()


@app.get("/imports")
def imports_page():
    managers_only()
    return render_template("home.html", quotes=[(q, store.quote_title(q)) for q in store.quote_files()])


@app.route("/projects/new", methods=["GET", "POST"])
def new_project():
    managers_only()
    errors = []
    if request.method == "POST":
        try:
            catalogue, messages, filename = prepare(request.form, request.files.get("chat"))
        except InvalidProject as exc:
            errors = exc.errors
        else:
            record = store.build_with_catalogue(
                store.new_job_id(catalogue.quote["job"]), messages, filename, catalogue,
            )
            flash(f"{record.title} added to Projects in progress. Review the detected changes.", "ok")
            return redirect(url_for("job_page", job_id=record.id))
    return render_template("new_project.html", values=request.form, errors=errors), 400 if errors else 200


@app.get("/guide")
def guide_page():
    return render_template("guide.html")


@app.post("/role")
def set_role():
    role = request.form.get("role", "pm")
    session["role"] = role if role in store.ROLE_LABELS else "pm"
    return redirect(url_for("workspace_page", persona=PERSONAS[session["role"]]["slug"]))


@app.post("/import")
def import_chat():
    managers_only()
    upload = request.files.get("chat")
    quote = request.form.get("quote", "")
    if not upload or not upload.filename.lower().endswith(".txt") or quote not in store.quote_files():
        flash("Choose a WhatsApp export (.txt) and the quote it belongs to.")
        return redirect(url_for("imports_page"))
    try:
        text = upload.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        flash("That file is not a WhatsApp text export.")
        return redirect(url_for("imports_page"))
    try:
        messages = parse_chat(text)
    except InvalidChatTimestamp as exc:
        flash(str(exc))
        return redirect(url_for("imports_page"))
    if not any(message.sender for message in messages):
        flash("No WhatsApp messages with sender names were found. Choose an export containing a conversation.")
        return redirect(url_for("imports_page"))
    record = store.build_from_messages(
        store.new_job_id(store.quote_title(quote)), messages, upload.filename, quote,
    )
    return redirect(url_for("job_page", job_id=record.id))


@app.post("/reset")
def reset():
    managers_only()
    store.reset_demo()
    flash("Demo data reset.")
    return redirect(url_for("home"))


@app.get("/whatsapp")
def whatsapp_page():
    """Connect the WhatsApp Business number and pick a group to read directly, instead of exporting it."""
    managers_only()  # the group list belongs to the business, not to one client or finance
    status = whatsapp_bridge.status()
    qr = status.get("qr") if str(status.get("qr") or "").startswith("data:image/png;base64,") else None
    groups, error = [], None
    if status.get("status") == "ready":
        try:
            groups = whatsapp_bridge.list_groups()
        except whatsapp_bridge.BridgeError as err:
            error = str(err)
    return render_template("whatsapp.html", status=status, qr=qr, groups=groups, error=error,
                           quotes=[(q, store.quote_title(q)) for q in store.quote_files()],
                           default_limit=whatsapp_bridge.DEFAULT_LIMIT, max_limit=whatsapp_bridge.MAX_LIMIT)


@app.post("/whatsapp/pair")
def whatsapp_pair():
    managers_only()
    phone = request.form.get("phone", "").strip()
    try:
        code = whatsapp_bridge.request_pairing_code(phone)
        flash(f"Pairing code: {code} — Enter this on your phone under 'Link with phone number instead'.", "ok")
    except whatsapp_bridge.BridgeError as err:
        flash(str(err))
    return redirect(url_for("whatsapp_page"))


@app.post("/whatsapp/import")
def whatsapp_import():
    managers_only()
    group_id = request.form.get("group", "")
    quote = request.form.get("quote", "")
    if not group_id or quote not in store.quote_files():
        flash("Choose a WhatsApp group and the quote it belongs to.")
        return redirect(url_for("whatsapp_page"))
    try:
        limit = int(request.form.get("limit") or whatsapp_bridge.DEFAULT_LIMIT)
        if not 1 <= limit <= whatsapp_bridge.MAX_LIMIT:
            raise ValueError
    except ValueError:
        flash(f"Messages to read must be a whole number from 1 to {whatsapp_bridge.MAX_LIMIT:,}.")
        return redirect(url_for("whatsapp_page"))
    try:
        name, messages = whatsapp_bridge.fetch_group(group_id, limit)
    except whatsapp_bridge.BridgeError as err:
        flash(str(err))
        return redirect(url_for("whatsapp_page"))
    if not messages:
        flash("No messages could be read from that group yet. Open it once on your phone, then try again.")
        return redirect(url_for("whatsapp_page"))
    record = store.build_from_messages(store.new_job_id(store.quote_title(quote)), messages,
                                       f"WhatsApp group: {name}", quote)
    flash(f"Read {len(messages):,} messages from {name}.", "ok")
    return redirect(url_for("job_page", job_id=record.id))


@app.get("/webhooks/whatsapp")
def webhook_verify():
    """Meta's one-time check when the webhook is registered: echo the challenge if the token matches."""
    token = os.environ.get("WHATSAPP_VERIFY_TOKEN")
    if token and request.args.get("hub.mode") == "subscribe" and request.args.get("hub.verify_token") == token:
        return request.args.get("hub.challenge", "")
    abort(403)


@app.post("/webhooks/whatsapp")
def webhook_receive():
    """Incoming WhatsApp messages from the official Cloud API. Meta expects a fast 200."""
    if not webhook.signature_ok(request.get_data(), request.headers.get("X-Hub-Signature-256")):
        abort(403)
    store.receive(request.get_json(silent=True) or {})
    return "ok"


@app.post("/job/<job_id>/live/next")
def live_next(job_id):
    """Demo only: deliver the next synthetic message of the live chat through the webhook path."""
    record = get_record(job_id)
    if redirect_client := staff_only(job_id):
        return redirect_client
    managers_only()
    count = 1 if request.form.get("all") != "1" else len(record.live.script if record.live else [])
    before = set(record.job.items)
    for _ in range(count):
        store.play_next(record)
    new = [k for k in record.job.items if k not in before]
    if new:
        flash(f"New in the chat: {', '.join(record.job.items[k].change.item for k in new)}.", "ok")
    return redirect(url_for("job_page", job_id=job_id) + "#chat-end")


@app.get("/job/<job_id>/history")
def history_page(job_id):
    """Quote versions, messages SMErgers sent, and the activity log, in one place."""
    record = get_record(job_id)
    if redirect_client := staff_only(job_id):
        return redirect_client
    return render_template("history.html", r=record, versions=record.versions, outbox=list(reversed(record.outbox)),
                           entries=record.job.log.entries, intact=record.job.log.intact(), guide=guide(record))


@app.get("/job/<job_id>/updates")
def updates_page(job_id):
    return redirect(url_for("history_page", job_id=job_id))


@app.post("/job/<job_id>/as/<role>")
def continue_as(job_id, role):
    """Demo: hand the job to the next person and open the page they would see."""
    if job_id not in store.JOBS:
        abort(404)
    session["role"] = role if role in store.ROLE_LABELS else "pm"
    if session["role"] == "client":
        session["client_job_id"] = job_id  # the client opens the link for this job
        return redirect(url_for("client_page", job_id=job_id))
    if session["role"] == "finance":
        return redirect(url_for("bill_page", job_id=job_id))
    return redirect(url_for("job_page", job_id=job_id))


GUIDE_STEPS = ["Messages arrive", "PM checks", "Director approves", "Client confirms", "Everyone in sync"]


def guide(record):
    """Where the job is in its journey, and who acts next: drives the guided demo bar."""
    team, items, role = record.team, record.job.items.values(), current_role()
    disputed = any(i.state == "disputed" for i in items)
    if record.live and record.live.script:
        step, who = 0, "pm"
        text = "New messages are waiting in the job's WhatsApp group. Press Next message to watch changes appear."
    elif any(needs(i, "pm") for i in items):
        step, who = 1, "pm"
        text = ("The client disputed a change. Use Show in chat to see who said what, then check it again."
                if disputed else f"{team['pm']} checks each change against its messages and adds any missing price.")
    elif any(needs(i, "owner") for i in items):
        step, who = 2, "owner"
        text = f"{team['owner']} approves the large or unusual changes {team['pm']} sent up."
    elif any(needs(i, "client") for i in items):
        step, who = 3, "client"
        text = "The client opens the link they got in WhatsApp and confirms or disputes each change."
    else:
        step, who = 4, None
        text = f"Done for now: quote version {record.versions[-1].number} was posted to the WhatsApp group."
    hand_over = None
    if who and who != role:
        label = "Open the client's link" if who == "client" else f"Continue as {team[who]} ({store.ROLE_LABELS[who]})"
        hand_over = (who, label)
    elif who is None and role == "client":
        hand_over = ("pm", f"Back to {team['pm']}: see the update in the group")
    return {"steps": GUIDE_STEPS, "step": step, "text": text, "hand_over": hand_over}


@app.get("/job/<job_id>")
def job_page(job_id):
    record = get_record(job_id)
    if redirect_client := staff_only(job_id):
        return redirect_client
    if current_role() == "finance":
        return redirect(url_for("bill_page", job_id=job_id))
    bill = build_bill(record.catalogue, record.job)
    show = request.args.get("show")
    highlighted = set(record.job.items[show].change.evidence_ids) if show in record.job.items else set()
    role = current_role()
    waiting = sum(1 for item in record.job.items.values() if needs(item, role))
    only_mine = request.args.get("view") == "mine"
    items = [(k, i) for k, i in record.job.items.items() if not only_mine or needs(i, role)]
    linked = {}  # message id -> change keys it is evidence for, so a message can point back to its change
    for k, i in record.job.items.items():
        for mid in i.change.evidence_ids:
            linked.setdefault(mid, []).append(k)
    return render_template("job.html", r=record, bill=bill, items=items, total_items=len(record.job.items),
                           allowed=allowed_actions, highlighted=highlighted, show=show, waiting=waiting,
                           only_mine=only_mine, owner_limit=record.job.policy["owner_approval_at"], linked=linked,
                           stages=progress(record.job), bulk=bulk_candidates(record.job, role),
                           suggestions=suggest.for_job(record) if role in ("pm", "owner") else [], guide=guide(record))


# One step of the journey per role; "do all" applies it to every change that is ready for it.
BULK = {"pm": ("review", "Check"), "owner": ("approve", "Approve"), "client": ("confirm", "Confirm")}
DONE = {"review": "Checked", "approve": "Approved", "confirm": "Confirmed"}


def bulk_candidates(job, role):
    """(action, label, keys, total RM) for the role's 'do all' button, or None."""
    if role not in BULK:
        return None
    action, label = BULK[role]
    keys = [k for k, i in job.items.items() if action in allowed_actions(i, role)
            and not (action == "review" and i.change.status == "unconfirmed")]  # those need a note each
    if not keys:
        return None
    return action, label, keys, sum(job.items[k].price or 0 for k in keys)


def progress(job):
    """How many changes sit at each stage of the journey, in order."""
    counts = {}
    for item in job.items.values():
        counts[item.state] = counts.get(item.state, 0) + 1
    stages = [("detected", "Found in chat"), ("reviewed", "Director to approve"), ("approved", "Client to confirm"),
              ("confirmed", "On the bill")]
    out = [(state, label, counts.get(state, 0)) for state, label in stages]
    if counts.get("disputed"):
        out.append(("disputed", "Disputed", counts["disputed"]))
    return out


@app.post("/job/<job_id>/bulk")
def bulk(job_id):
    record = get_record(job_id)
    role = current_role()
    if role == "finance":
        abort(403)
    candidates = bulk_candidates(record.job, role)
    if candidates is None:
        flash("Nothing is ready for that.")
        return redirect(local_return_path(request.form.get("next"), url_for("job_page", job_id=job_id)))
    action, label, keys, total = candidates
    actor = record.actor(role)
    done = []
    for key in keys:
        try:
            record.job.act(key, action, actor)
            done.append(key)
        except NotAllowed as err:
            flash(f"{record.job.items[key].change.item}: {err}")
    sync.after_actions(record, action, done, actor)
    done_total = sum(record.job.items[key].price or 0 for key in done)
    if done:
        flash(f"{DONE[action]} {len(done)} change{'' if len(done) == 1 else 's'} ({rm(done_total)}).", "ok")
    return redirect(local_return_path(request.form.get("next"), url_for("job_page", job_id=job_id)))


@app.post("/job/<job_id>/act/<key>")
def act(job_id, key):
    record = get_record(job_id)
    if current_role() == "finance":
        abort(403)
    if key not in record.job.items:
        abort(404)
    price = request.form.get("price", "").replace(",", "").replace("RM", "").strip()
    action, actor = request.form.get("action", ""), record.actor(current_role())
    try:
        item = record.job.act(key, action, actor,
                              price=float(price) if price else None, note=request.form.get("note", "").strip())
        sync.after_actions(record, action, [key], actor)
        flash(f"{item.change.item}: {STATE_LABELS[item.state].lower()}.", "ok")
    except NotAllowed as err:
        flash(str(err))
    except (KeyError, ValueError):
        flash("That action could not be done. Check the price is a number.")
    return redirect(local_return_path(request.form.get("next"), url_for("job_page", job_id=job_id, show=key)))


@app.get("/job/<job_id>/bill")
def bill_page(job_id):
    record = get_record(job_id)
    if redirect_client := staff_only(job_id):
        return redirect_client
    return render_template("bill.html", r=record, bill=build_bill(record.catalogue, record.job), guide=guide(record))


@app.get("/job/<job_id>/bill.csv")
def bill_csv(job_id):
    """The draft bill as CSV, to import into the company's accounting software."""
    record = get_record(job_id)
    if redirect_client := staff_only(job_id):
        return redirect_client
    bill = build_bill(record.catalogue, record.job)
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["DRAFT - not an invoice", bill.quote_id, record.catalogue.quote["client"]])
    writer.writerow(["section", "item", "qty", "unit", "unit_price", "amount", "source_changes"])
    for l in bill.quote_lines:
        writer.writerow(["quote", l.label, f"{l.qty:g}", l.unit, l.unit_price, l.amount, " ".join(l.change_keys)])
    for l in bill.change_lines:
        writer.writerow(["agreed change", l.label, f"{l.qty:g}", "", "", l.amount, " ".join(l.change_keys)])
    writer.writerow(["total", "Draft total", "", "", "", bill.draft_total, ""])
    snapshots = dict(session.get("bill_exports", {}))
    snapshots.pop(record.id, None)
    snapshots[record.id] = record.job.log.entries[-1].hash  # export is current until the next recorded action
    session["bill_exports"] = dict(list(snapshots.items())[-20:])
    return Response(out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename={job_id}-draft-bill.csv"})


@app.get("/job/<job_id>/client")
def client_page(job_id):
    record = get_record(job_id)
    if current_role() == "client":
        session["client_job_id"] = job_id
    shown = [(k, i) for k, i in record.job.items.items() if i.state in ("approved", "confirmed", "disputed")]
    by_id = {m.id: m for m in record.messages}
    return render_template("client.html", r=record, items=shown, by_id=by_id, allowed=allowed_actions,
                           bulk=bulk_candidates(record.job, current_role()) if current_role() == "client" else None,
                           guide=guide(record))


@app.get("/job/<job_id>/log")
def log_page(job_id):
    record = get_record(job_id)
    if redirect_client := staff_only(job_id):
        return redirect_client
    return redirect(url_for("history_page", job_id=job_id) + "#log")


@app.get("/job/<job_id>/evidence/<key>")
def evidence_page(job_id, key):
    """Read-only source evidence, including for finance; never offers editing controls."""
    record = get_record(job_id)
    if current_role() == "client":
        return redirect(url_for("client_page", job_id=job_id, _anchor=f"c-{key}"))
    item = record.job.items.get(key)
    if item is None:
        abort(404)
    evidence_ids = set(item.change.evidence_ids)
    return render_template(
        "evidence.html", r=record, item=item, key=key,
        messages=[message for message in record.messages if message.id in evidence_ids],
    )


@app.get("/api/jobs/<job_id>")
def job_api(job_id):
    """Read-only job summary in the shape we assume Orbyte's hub would consume (docs/orbyte-integration.md)."""
    if current_role() == "client":
        abort(403)
    record = get_record(job_id)
    bill = build_bill(record.catalogue, record.job)
    return jsonify({
        "job": {"id": record.id, "title": record.title, "client": record.catalogue.quote["client"],
                "quote_id": bill.quote_id, "simulated": True},
        "changes": [{
            "key": k, "item": i.change.item, "kind": i.change.kind, "quote_line": i.change.line_id,
            "qty_delta": i.change.qty_delta, "price": i.price, "found_as": i.change.status,
            "approval_state": i.state, "confidence": i.change.confidence, "reason": i.change.reason,
            "evidence_message_ids": i.change.evidence_ids,
        } for k, i in record.job.items.items()],
        "bill": {"quote_total": bill.quote_total, "confirmed_changes": bill.changes_total,
                 "draft_total": bill.draft_total, "not_on_bill_yet": bill.outstanding_priced_total,
                 "agreed_in_chat_beyond_quote": bill.agreed_beyond_quote},
        "activity_log": {"intact": record.job.log.intact(), "entries": [vars(e) for e in record.job.log.entries]},
        "suggestions": [vars(s) for s in suggest.for_job(record)],
    })


NEXT_STEP = {"pm": {"review", "set_price"}, "owner": {"approve", "decide"}, "client": {"confirm"}}


def needs(item, role):
    """True if this change waits for this role's own next step. Reject and dispute are always
    possible, and the owner may also price a change, so those do not count as work waiting."""
    return bool(set(allowed_actions(item, role)) & NEXT_STEP.get(role, set()))


def allowed_actions(item, role):
    """Actions to offer this role for this change. The engine checks again on submit;
    this only hides buttons that could not succeed yet."""
    actions = [a for a, (roles, states) in ACTIONS.items() if role in roles and item.state in states]
    if item.price is None:
        actions = [a for a in actions if a != "review"]
    elif item.state != "disputed":
        actions = [a for a in actions if a != "set_price"]
    if item.change.kind == "discount":
        actions = [a for a in actions if a not in ("review", "set_price")]
    else:
        actions = [a for a in actions if a != "decide"]
    return actions


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
