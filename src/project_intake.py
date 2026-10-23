"""Validate project input before passing it to the existing change-detection engine."""
from datetime import date
from decimal import Decimal, InvalidOperation

from catalogue import Catalogue
from chat_import import parse_chat


class InvalidProject(ValueError):
    def __init__(self, errors):
        self.errors = errors


def prepare(form, upload=None):
    errors = []

    def text(name, label):
        value = form.get(name, "").strip()
        if not value or len(value) > 200:
            errors.append(f"{label} is required and must be at most 200 characters.")
        return value

    quote = {key: text(field, label) for key, field, label in [
        ("job", "title", "Project name"), ("client", "client", "Client"),
        ("company", "company", "Company"), ("quote_id", "quote_id", "Quote reference"),
        ("event_type", "event_type", "Event type"),
    ]}
    quote["team"] = {role: text(role, label) for role, label in [
        ("pm", "Project manager"), ("owner", "Project director"), ("finance", "Finance contact"),
    ]}
    quote["event_date"] = form.get("event_date", "").strip()
    try:
        date.fromisoformat(quote["event_date"])
    except ValueError:
        errors.append("Enter a valid event date.")
    quote["currency"] = "RM"
    quote["label"] = "User-entered prototype data"

    def number(raw, label, positive=False):
        try:
            value = Decimal(raw.strip())
            if not value.is_finite() or value < 0 or value > 1_000_000_000 or (positive and value == 0):
                raise ValueError
            return float(value)
        except (InvalidOperation, ValueError):
            errors.append(f"{label} must be {'positive' if positive else 'non-negative'} and at most 1,000,000,000.")
            return 0

    def rows(extra=False):
        names = ["extra_item", "extra_unit", "extra_price", "extra_aliases"] if extra else [
            "item", "unit", "unit_price", "aliases", "qty"]
        columns = [form.getlist(name) for name in names]
        count = max(map(len, columns), default=0)
        label = "Rate-card extra" if extra else "Quote line"
        if count > 100 or any(len(col) != count for col in columns):
            errors.append(f"{label} rows are incomplete or exceed the limit of 100.")
            return []
        result = []
        for index, values in enumerate(zip(*columns), 1):
            if extra and not any(v.strip() for v in values):
                continue
            item, unit, price, aliases = [v.strip() for v in values[:4]]
            if not item or not unit or len(item) > 200 or len(unit) > 50:
                errors.append(f"{label} {index} needs an item (up to 200 characters) and unit (up to 50).")
            words = list(dict.fromkeys([item] + [a.strip() for a in aliases.split(",") if a.strip()]))
            if len(words) > 30 or any(len(a) > 200 for a in words):
                errors.append(f"{label} {index} has too many or overly long aliases.")
            row = dict(item=item, unit=unit, unit_price=number(price, f"{label} {index} price"), aliases=words)
            if not extra:
                row.update(id=f"L{index:02}", qty=number(values[4], f"{label} {index} quantity", positive=True))
            result.append(row)
        return result

    quote["lines"] = rows()
    quote["rate_card"] = rows(extra=True)
    if not quote["lines"]:
        errors.append("Add at least one original quote line.")
    chat = form.get("chat_text", "").strip()
    filename = "Pasted WhatsApp export"
    if upload and upload.filename:
        if chat:
            errors.append("Use either a pasted chat or a file, not both.")
        if not upload.filename.lower().endswith(".txt"):
            errors.append("Choose a WhatsApp .txt export.")
        try:
            chat = upload.read().decode("utf-8-sig")
        except UnicodeDecodeError:
            errors.append("The chat file must be UTF-8 text.")
        filename = upload.filename.replace("\\", "/").split("/")[-1][:200]
    messages = parse_chat(chat)
    if not any(m.sender for m in messages):
        errors.append("Provide a WhatsApp export with dated messages and sender names.")
    if errors:
        raise InvalidProject(errors)
    return Catalogue(quote), messages, filename
