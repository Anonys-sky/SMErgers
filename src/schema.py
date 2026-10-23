"""The data contract. Every extractor (rules, AI, cached) must produce these shapes,
so the matcher, approval flow and UI never need to know which one ran."""
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
