"""Web app. All decisions happen in the engine modules; these routes only call them and render."""
import csv
import io
import os
import secrets

from flask import Flask, Response, abort, flash, jsonify, redirect, render_template, request, session, url_for

import store
from bill import build_bill
from schema import STATUSES
from workflow import ACTIONS, STATE_LABELS, NotAllowed

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(16)
app.config["MAX_CONTENT_LENGTH"] = 1_000_000  # chat exports are small text files

store.reset_demo()


def current_role():
    role = session.get("role", "pm")
    return role if role in store.ROLE_LABELS else "pm"


def get_record(job_id):
    record = store.JOBS.get(job_id)
    if record is None:
        abort(404)
    return record


def staff_only(job_id):
    """Clients only ever see their confirmation page, never the team's internal views."""
    if current_role() == "client":
        return redirect(url_for("client_page", job_id=job_id))
    return None


@app.template_filter("rm")
def rm(value):
    if value is None:
        return "No price yet"
    sign = "−" if value < 0 else ""
    return f"{sign}RM{abs(value):,.2f}".replace(".00", "")


@app.context_processor
def shared():
    return {"role": current_role(), "roles": store.ROLE_LABELS, "state_labels": STATE_LABELS,
            "status_labels": STATUSES}


@app.get("/")
def home():
    rows = [(r, build_bill(r.catalogue, r.job)) for r in store.JOBS.values()]
    return render_template("home.html", rows=rows, quotes=[(q, store.quote_title(q)) for q in store.quote_files()])


@app.post("/role")
def set_role():
    role = request.form.get("role", "pm")
    session["role"] = role if role in store.ROLE_LABELS else "pm"
    return redirect(request.form.get("next") or url_for("home"))


@app.post("/import")
def import_chat():
    upload = request.files.get("chat")
    quote = request.form.get("quote", "")
    if not upload or not upload.filename.lower().endswith(".txt") or quote not in store.quote_files():
        flash("Choose a WhatsApp export (.txt) and the quote it belongs to.")
        return redirect(url_for("home"))
    try:
        text = upload.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        flash("That file is not a WhatsApp text export.")
        return redirect(url_for("home"))
    record = store.build(store.new_job_id(store.quote_title(quote)), text, upload.filename, quote)
    if not record.messages:
        flash("No WhatsApp messages were found in that file.")
    return redirect(url_for("job_page", job_id=record.id))


@app.post("/reset")
def reset():
    store.reset_demo()
    flash("Demo data reset.")
    return redirect(url_for("home"))


@app.get("/job/<job_id>")
def job_page(job_id):
    record = get_record(job_id)
    if redirect_client := staff_only(job_id):
        return redirect_client
    bill = build_bill(record.catalogue, record.job)
    show = request.args.get("show")
    highlighted = set(record.job.items[show].change.evidence_ids) if show in record.job.items else set()
    waiting = sum(1 for item in record.job.items.values() if allowed_actions(item, current_role()))
    return render_template("job.html", r=record, bill=bill, items=list(record.job.items.items()),
                           allowed=allowed_actions, highlighted=highlighted, show=show, waiting=waiting,
                           owner_limit=record.job.policy["owner_approval_at"])


@app.post("/job/<job_id>/act/<key>")
def act(job_id, key):
    record = get_record(job_id)
    if key not in record.job.items:
        abort(404)
    price = request.form.get("price", "").replace(",", "").replace("RM", "").strip()
    try:
        record.job.act(key, request.form.get("action", ""), record.actor(current_role()),
                       price=float(price) if price else None, note=request.form.get("note", "").strip())
    except NotAllowed as err:
        flash(str(err))
    except (KeyError, ValueError):
        flash("That action could not be done. Check the price is a number.")
    return redirect(request.form.get("next") or url_for("job_page", job_id=job_id, show=key))


@app.get("/job/<job_id>/bill")
def bill_page(job_id):
    record = get_record(job_id)
    if redirect_client := staff_only(job_id):
        return redirect_client
    return render_template("bill.html", r=record, bill=build_bill(record.catalogue, record.job))


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
    return Response(out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename={job_id}-draft-bill.csv"})


@app.get("/job/<job_id>/client")
def client_page(job_id):
    record = get_record(job_id)
    shown = [(k, i) for k, i in record.job.items.items() if i.state in ("approved", "confirmed", "disputed")]
    by_id = {m.id: m for m in record.messages}
    return render_template("client.html", r=record, items=shown, by_id=by_id, allowed=allowed_actions)


@app.get("/job/<job_id>/log")
def log_page(job_id):
    record = get_record(job_id)
    if redirect_client := staff_only(job_id):
        return redirect_client
    return render_template("log.html", r=record, entries=record.job.log.entries, intact=record.job.log.intact())


@app.get("/api/jobs/<job_id>")
def job_api(job_id):
    """Read-only job summary in the shape we assume Orbyte's hub would consume (docs/orbyte-integration.md)."""
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
    })


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
    return actions


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
