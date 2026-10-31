"""The data contract. Every extractor (rules, AI, cached) must produce these shapes,
so the matcher, approval flow and UI never need to know which one ran."""
import re
from dataclasses import dataclass, field
from datetime import datetime

# What happened to a change, in the words shown to users.
STATUSES = {
    "ready": "Ready for approval",
    "needs_price": "Needs a price",
    "needs_decision": "Project director decides the amount",
    "unconfirmed": "Not agreed in the chat yet",
    "withdrawn": "Withdrawn",
    "log_only": "No cost change",
}


@dataclass(frozen=True)
class Message:
    id: str                 # stable hash, so importing the same chat twice never duplicates anything
    seq: int                # position in the chat, for display order
    sent_at: datetime       # local time as exported; WhatsApp exports carry no timezone
    sender: str | None      # None for system notices such as the encryption banner
    text: str
    is_media: bool = False


@dataclass
class Change:
    key: str
    kind: str
    item: str
    line_id: str | None
    qty_delta: float
    price_delta: float | None   # None means nobody stated or quoted a price
    status: str
    evidence_ids: list[str] = field(default_factory=list)
    confidence: str = "medium"  # high / medium / low, shown next to the change
    reason: str = ""            # plain-language explanation for the reviewer
    source: str = "rules"       # rules / ai / cache


_GENERIC = {"mor", "ext", "add", "upg", "cha", "and", "for", "the", "can", "not", "tha", "ple", "ok"}


def _stems(text):
    return {w[:3] for w in re.findall(r"[a-zA-Z]{3,}", text.lower())} - _GENERIC


def request_match_score(a, b):
    """How strongly two Changes read from the same chat are the same request, 0 if they are not.
    Two readers (rules and AI) name and number things differently, so the test is the chat messages they
    cite: they must share at least one, point the same way (more or fewer), and be about the same thing."""
    shared_evidence = len(set(a.evidence_ids) & set(b.evidence_ids))
    if not shared_evidence:
        return 0
    if a.qty_delta and b.qty_delta and (a.qty_delta > 0) != (b.qty_delta > 0):
        return 0
    same_line = bool(a.line_id) and a.line_id == b.line_id
    shared_words = _stems(a.item) & _stems(b.item)
    if not (same_line or shared_words):
        return 0
    return shared_evidence * 10 + (3 if same_line else 0) + len(shared_words)
