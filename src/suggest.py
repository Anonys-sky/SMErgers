"""Suggestions from past jobs: what usually changes late in this kind of event, and what to put
in the quote so it is decided upfront instead of in the chat at the last minute.

Plain counting over the company's job history, so every suggestion can be checked by hand.
A trained model can replace the counting once real, human-approved history exists.
"""
import json
from dataclasses import dataclass
from statistics import median

from catalogue import DATA

MIN_JOBS = 2  # a pattern needs at least this many past jobs before we suggest anything

# What the late change was, and the one step that moves the decision into the quote.
ADVICE = {
    "guests": ("Guest count went up", "Set a final headcount date and a price per extra guest in the quote."),
    "overtime": ("Event ran past the planned end", "Put hourly overtime rates for emcee, crew and photographer in the quote."),
    "av_extras": ("Extra mics or AV on the day", "Add spare wireless mics and their price to the rate card."),
    "screen": ("Bigger screen or LED wall", "Offer the bigger screen as a priced option in the quote."),
    "signage": ("More banners, backdrop or signage", "Price extra banners and a larger backdrop in the rate card."),
    "staffing": ("More hostesses or crew", "Price extra staff per person in the rate card."),
    "rehearsal": ("Extra rehearsal", "Offer an extra rehearsal session as a priced option."),
    "giveaways": ("More door gifts or swag", "Quote a per-piece price for extra door gifts."),
    "discount": ("Discount given in the chat", "Decide your discount policy before the client asks for one."),
}


@dataclass
class Suggestion:
    category: str
    title: str
    seen_in: int
    of_jobs: int
    typical_amount: float
    typical_days_before: float
    unpriced: int
    advice: str

    @property
    def share(self):
        return self.seen_in / self.of_jobs


def history():
    return json.loads((DATA / "history" / "past_jobs.json").read_text(encoding="utf-8"))


def for_event_type(event_type, company=None, data=None):
    """Suggestions for one kind of event, most frequent first. Empty when history is too thin."""
    data = data or history()
    if company and data.get("company") != company:
        return []
    jobs = [j for j in data["jobs"] if j["event_type"] == event_type]
    if len(jobs) < MIN_JOBS:
        return []
    by_category = {}
    for job in jobs:
        for change in job["late_changes"]:
            by_category.setdefault(change["category"], []).append((job["id"], change))
    out = []
    for category, hits in by_category.items():
        seen_in = len({job_id for job_id, _ in hits})
        if seen_in < MIN_JOBS or category not in ADVICE:
            continue
        title, advice = ADVICE[category]
        changes = [c for _, c in hits]
        out.append(Suggestion(
            category, title, seen_in, len(jobs),
            typical_amount=median(c["amount"] for c in changes),
            typical_days_before=median(c["days_before"] for c in changes),
            unpriced=sum(1 for c in changes if not c["priced_in_chat"]),
            advice=advice,
        ))
    out.sort(key=lambda s: (s.share, abs(s.typical_amount)), reverse=True)
    return out


def for_job(record):
    quote = record.catalogue.quote
    return for_event_type(quote.get("event_type"), quote.get("company"))
