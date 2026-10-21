"""The job's catalogue: quote lines plus rate-card extras, and how chat words map to them.
Kept as data (the quote JSON) so another sector only needs a new quote file, not new code."""
import json
import re
from dataclasses import dataclass
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"


@dataclass(frozen=True)
class Entry:
    item: str
    unit: str
    unit_price: float
    aliases: tuple[str, ...]
    line_id: str | None = None   # None for rate-card extras that are not on the quote
    qty: float = 0


def _alias_pattern(alias):
    # Word boundaries do not exist in Chinese text, so only apply them to Latin aliases.
    escaped = re.escape(alias)
    return re.compile(escaped if not alias.isascii() else rf"\b{escaped}\b", re.I)


class Catalogue:
    def __init__(self, quote):
        self.quote = quote
        self.lines = [
            Entry(l["item"], l["unit"], l["unit_price"], tuple(l["aliases"]), l["id"], l["qty"])
            for l in quote["lines"]
        ]
        self.extras = [
            Entry(r["item"], r["unit"], r["unit_price"], tuple(r["aliases"]))
            for r in quote.get("rate_card", [])
        ]
        self._patterns = {e: [_alias_pattern(a) for a in e.aliases] for e in self.lines + self.extras}

    @classmethod
    def load(cls, quote_file):
        return cls(json.loads((DATA / "quotes" / quote_file).read_text(encoding="utf-8")))

    def line(self, line_id):
        return next((e for e in self.lines if e.line_id == line_id), None)

    def mentions(self, text):
        """Entries named in the text, best match first (most aliases hit, then longest alias)."""
        scored = []
        for entry, patterns in self._patterns.items():
            hits = [p.pattern for p in patterns if p.search(text)]
            if hits:
                scored.append((len(hits), max(len(h) for h in hits), entry))
        scored.sort(key=lambda s: (s[0], s[1]), reverse=True)
        return [entry for _, _, entry in scored]

    def extra_for(self, entry):
        """The rate-card extra that extends a quote line, e.g. emcee -> emcee overtime."""
        base = entry.item.split()[0].lower()
        return next((x for x in self.extras if x.item.lower().startswith(base)), None)
