"""Role-specific presentation data, derived from the existing approval and bill engines."""
from collections import Counter

from flask import url_for

from bill import build_bill


PERSONAS = {
    "pm": {
        "slug": "project-manager", "title": "Project Manager", "initials": "PM",
        "subtitle": "Project delivery",
        "headline": "Every change, under control.",
        "description": "Bring in conversations, verify the evidence and prepare changes for approval.",
        "steps": [
            "Import a WhatsApp text export and choose the matching existing quote.",
            "Open a project and use Show in chat to compare each change with its source messages.",
            "Add missing prices, then mark the changes checked. Unconfirmed agreements need a note.",
            "The project director approves exceptions; the client confirms before a change reaches the bill.",
        ],
    },
    "owner": {
        "slug": "project-director", "title": "Project Director", "initials": "PD",
        "subtitle": "Approvals & oversight",
        "headline": "Make the decisions that move work forward.",
        "description": "Review high-value changes, resolve exceptions and keep project approvals moving.",
        "steps": [
            "Review your decision queue and open a project to inspect the supporting chat.",
            "Approve PM-checked changes at or above the project's approval limit.",
            "Use Decide with an amount and explanation for discounts, disputes or unusual changes.",
            "Track client confirmation. Approved changes are not billable until the client confirms.",
        ],
    },
    "client": {
        "slug": "client", "title": "Client", "initials": "CL",
        "subtitle": "Your project",
        "headline": "Know exactly what you are agreeing to.",
        "description": "Review proposed changes, compare the original messages and confirm the agreed amount.",
        "steps": [
            "Open Changes to confirm to see the items the event team has approved for your review.",
            "Read each description, amount and supporting WhatsApp message.",
            "Choose Confirm when it matches your agreement, or Dispute and explain what needs correcting.",
            "Confirmed changes become part of the draft bill. This page does not take payments.",
        ],
    },
    "finance": {
        "slug": "finance", "title": "Finance", "initials": "FN",
        "subtitle": "Billing & reconciliation",
        "headline": "Prepare the bill with confidence.",
        "description": "Reconcile confirmed changes, check what is excluded and export draft bills for accounting.",
        "steps": [
            "Open a project's draft bill to compare the original quote with client-confirmed changes.",
            "Review Not on the bill yet. Unpriced, disputed and unconfirmed changes are excluded.",
            "Check the activity log for the review, director approval and client-confirmation history.",
            "Print the draft or export its CSV for accounting software. No invoice is sent from this app.",
        ],
    },
}


def build_workspace(role, records, needs, exported_jobs=()):
    """Create dashboard totals, queues and completion steps from current job state.
    `needs(item, role)` is the app's rule for whether a change waits for this role's own next step."""
    jobs, queue, activity = [], [], []
    counts = Counter()
    money = Counter()
    for record in records:
        bill = build_bill(record.catalogue, record.job)
        states = Counter(item.state for item in record.job.items.values())
        actionable = [(key, item) for key, item in record.job.items.items() if needs(item, role)]
        pending = sum(states[state] for state in ("detected", "reviewed", "approved", "disputed"))
        missing_price = sum(
            item.price is None and item.state not in ("record_only", "rejected", "confirmed")
            for item in record.job.items.values()
        )
        endpoint = "client_page" if role == "client" else "bill_page" if role == "finance" else "job_page"
        primary_url = url_for(endpoint, job_id=record.id)
        status = (
            "Disputed" if states["disputed"] else
            "Needs a price" if missing_price and role != "client" else
            "Needs your review" if actionable else
            "Awaiting confirmation" if states["approved"] else
            "In review" if pending else "Up to date"
        )
        jobs.append({
            "record": record, "bill": bill, "title": record.title,
            "client": record.catalogue.quote["client"], "waiting": len(actionable),
            "confirmed": states["confirmed"], "disputed": states["disputed"],
            "missing_price": missing_price, "changes": len(record.job.items),
            "pending": pending, "status": status, "primary_url": primary_url,
            "exported": record.id in exported_jobs,
        })
        for key, item in actionable:
            queue.append({
                "record": record, "key": key, "item": item,
                "url": (
                    url_for("client_page", job_id=record.id, _anchor=f"c-{key}")
                    if role == "client" else url_for("job_page", job_id=record.id, show=key)
                ),
            })
        for entry in record.job.log.entries:
            if role == "client" and entry.action not in ("confirm", "dispute"):
                continue
            activity.append({
                "entry": entry, "project": record.title,
                "url": primary_url if role == "client" else url_for("history_page", job_id=record.id, _anchor="log"),
            })
        counts.update(states)
        counts["missing_price"] += missing_price
        counts["pending"] += pending
        money["quote"] += bill.quote_total
        money["draft"] += bill.draft_total
        money["confirmed"] += bill.changes_total
        money["excluded"] += bill.outstanding_priced_total
        money["awaiting_client"] += sum(
            item.price or 0 for item in record.job.items.values() if item.state == "approved"
        )

    activity.sort(key=lambda event: (event["entry"].at, event["entry"].seq), reverse=True)
    queue.sort(key=lambda row: (
        {"disputed": 0, "reviewed": 1, "approved": 2, "detected": 3}.get(row["item"].state, 4),
        row["item"].price is not None,
    ))
    base = url_for("workspace_page", persona=PERSONAS[role]["slug"])
    task_url = base + "?view=tasks"
    projects_url = base + "?view=projects"

    def metric(label, value, hint, kind="number"):
        return {"label": label, "value": round(value, 2), "kind": kind, "hint": hint}

    if role == "pm":
        metrics = [
            metric("Active projects", len(jobs), "Projects in this demo session"),
            metric("Changes to review", len(queue), "Review or pricing action available"),
            metric("Missing prices", counts["missing_price"], "Need individual attention"),
            metric("Confirmed changes", money["confirmed"], "Already included in draft bills", "money"),
        ]
        checklist = [
            ("Bring in the conversation", "Import a text export with its matching quote.", bool(jobs), url_for("imports_page")),
            ("Complete the pricing", "Add amounts to unpriced changes.", counts["missing_price"] == 0, task_url),
            ("Check the changes", "Review the source and mark each change checked.", len(queue) == 0, task_url),
            ("Follow up on confirmations", "Director approval comes before client confirmation.", counts["pending"] == 0, projects_url),
        ]
    elif role == "owner":
        metrics = [
            metric("Priced changes found in chat", money["confirmed"] + money["excluded"], "On top of the signed quotes: on the bill plus waiting", "money"),
            metric("On the bill", money["confirmed"], "Confirmed by the client", "money"),
            metric("Waiting to reach the bill", money["excluded"], "Priced, not yet confirmed", "money"),
            metric("Needs your decision", len(queue), "Approve, reject or decide, from the queue below"),
        ]
        checklist = [
            ("Clear the decision queue", "Compare each decision with its source messages.", len(queue) == 0, task_url),
            ("Approve checked changes", "Review the items waiting for director sign-off.", counts["reviewed"] + counts["detected"] == 0, task_url),
            ("Resolve disputed changes", "Record a clear decision and the agreed amount.", counts["disputed"] == 0, task_url),
            ("Follow client confirmation", "Only client-confirmed changes reach a draft bill.", counts["pending"] == 0, projects_url),
        ]
    elif role == "client":
        metrics = [
            metric("Ready to confirm", counts["approved"], "Approved by the event team"),
            metric("Awaiting your agreement", money["awaiting_client"], "Review the evidence before confirming", "money"),
            metric("Confirmed", counts["confirmed"], "Your confirmed changes"),
            metric("Disputed", counts["disputed"], "Returned to the team for correction"),
        ]
        checklist = [
            ("Receive reviewed changes", "The event team sends approved items for your review.", counts["approved"] + counts["confirmed"] + counts["disputed"] > 0, task_url),
            ("Confirm agreed amounts", "Compare the amount with the original messages.", counts["approved"] == 0 and counts["confirmed"] > 0, task_url),
            ("Resolve any disputes", "Explain issues so the team can correct them.", counts["disputed"] == 0 and counts["confirmed"] > 0, projects_url),
            ("Keep a confirmation record", "Your confirmed changes remain available to review.", counts["confirmed"] > 0, projects_url),
        ]
    else:
        metrics = [
            metric("Draft bill total", money["draft"], "Original quotes plus confirmed changes", "money"),
            metric("Confirmed changes", money["confirmed"], "Included in the draft totals", "money"),
            metric("Excluded changes", money["excluded"], "Priced but not fully confirmed", "money"),
            metric("Unpriced changes", counts["missing_price"], "Excluded until priced and approved"),
        ]
        checklist = [
            ("Reconcile confirmed changes", "Confirmations are required before extras reach billing.", counts["pending"] == 0, projects_url),
            ("Check excluded changes", "Pending or disputed items must stay out of billing.", counts["pending"] == 0, projects_url),
            ("Resolve missing prices", "Ask the project team to price outstanding changes.", counts["missing_price"] == 0, projects_url),
            ("Export the latest drafts", "Export each current draft as a CSV for accounting.", bool(jobs) and all(row["exported"] for row in jobs), projects_url),
        ]
    limits = {}
    for record in records:
        limits.setdefault(record.job.policy["owner_approval_at"], []).append(record.title)
    return {
        "limits": sorted(limits.items()),
        "jobs": jobs, "queue": queue, "activity": activity[:12], "metrics": metrics,
        "checklist": [
            {"title": title, "description": description, "complete": complete, "url": url}
            for title, description, complete, url in checklist
        ],
        "completion": round(100 * sum(row[2] for row in checklist) / len(checklist)),
    }
