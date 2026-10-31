"""Talks to the local WhatsApp bridge (whatsapp/bridge.js), which reads groups through whatsapp-web.js.

Standard library only, so requirements.txt stays the same. Settings (environment variables):
  WHATSAPP_BRIDGE_URL  where the bridge listens (default http://127.0.0.1:3001)
  WHATSAPP_TIMEZONE    time zone for message times, e.g. Asia/Kuala_Lumpur
                       (default: this computer's time zone, which is what an export shows)
"""
import json
import os
import logging
import threading
from dataclasses import dataclass, field, replace
from datetime import datetime
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from chat_import import messages_from_whatsapp
from workflow import SYSTEM

DEFAULT_URL = "http://127.0.0.1:3001"
DEFAULT_LIMIT = 2000
MAX_LIMIT = 20000
START_HINT = "Start both services with npm start (or just the bridge with npm run whatsapp). For the published app, republish with the configured build and run commands."


class BridgeError(Exception):
    """Something the user can act on, worded for the screen."""


def base_url():
    return os.environ.get("WHATSAPP_BRIDGE_URL", DEFAULT_URL).rstrip("/")


def timezone():
    name = os.environ.get("WHATSAPP_TIMEZONE", "").strip()
    if not name:
        return None
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as err:
        raise BridgeError(f"WHATSAPP_TIMEZONE '{name}' is not a known time zone.") from err


def _get(path, timeout):
    try:
        with urllib.request.urlopen(base_url() + path, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        try:
            detail = json.loads(err.read().decode("utf-8")).get("error")
        except (ValueError, AttributeError):
            detail = None
        raise BridgeError(detail or f"The WhatsApp bridge answered with error {err.code}.") from err
    except (urllib.error.URLError, ConnectionError, TimeoutError) as err:
        reason = getattr(err, "reason", err)
        if isinstance(reason, TimeoutError) or isinstance(err, TimeoutError):
            raise BridgeError("WhatsApp took too long to answer. Try again, or read fewer messages.") from err
        raise BridgeError(f"The WhatsApp bridge is not running at {base_url()}. {START_HINT}") from err
    except ValueError as err:
        raise BridgeError("The WhatsApp bridge sent a reply that is not JSON.") from err


def status():
    """Bridge state; never raises. status is 'offline' when the bridge is not running."""
    try:
        return _get("/status", timeout=3)
    except BridgeError as err:
        return {"status": "offline", "error": str(err), "qr": None, "me": None, "loading": None}


def list_groups():
    return _get("/groups", timeout=60)["groups"]


def fetch_group(group_id, limit=DEFAULT_LIMIT):
    """Read initial history plus messages captured since this group was selected."""
    if not isinstance(group_id, str) or not group_id.endswith("@g.us"):
        raise BridgeError("Choose a WhatsApp group.")
    limit = max(1, min(int(limit), MAX_LIMIT))
    tz = timezone()  # checked before the slow read, so a bad setting fails fast
    path = f"/groups/{urllib.parse.quote(group_id, safe='')}/messages?limit={limit}"
    data = _get(path, timeout=600)  # a long group history takes a while to load
    return data["group"]["name"], messages_from_whatsapp(data["messages"], tz)


@dataclass
class GroupSync:
    group_id: str
    limit: int
    error: str = ""
    checked_at: object = None
    lock: object = field(default_factory=threading.RLock, repr=False, compare=False)
    ai_running: bool = False        # an AI refinement is in progress for this group
    ai_dirty: bool = False          # newer messages arrived while it ran: read once more afterwards
    ai_failed: bool = False         # the last AI attempt failed (logged once, not on every message)


_worker = None
_worker_lock = threading.Lock()
_poll_lock = threading.Lock()


def apply_messages(record, incoming):
    """Register each message once and re-read the real group without resetting decisions."""
    import store
    import sync

    with record.bridge.lock:
        known = {m.id for m in record.messages}
        merged = {m.id: m for m in record.messages}
        merged.update((m.id, m) for m in incoming)
        messages = [replace(m, seq=i) for i, m in enumerate(
            sorted(merged.values(), key=lambda m: m.sent_at), 1)]
        if messages == record.messages:
            return []
        # Read with the rules first, always: it is instant and needs no network. If this project asked for
        # the AI reader, the AI reads the same chat in the background and refines the answer (refine_async).
        changes = store.extract(messages, record.catalogue, ai=False)
        for message in messages:
            if message.id not in known:
                record.job.log.add(datetime.now(), SYSTEM, "trigger", "-",
                                   f"message from {message.sender} registered through the WhatsApp bridge")
        if record.ai:
            new = record.job.reconcile(changes, prefer_incoming=False)
        else:
            new = record.job.refresh(changes)
        record.messages = messages
        sync.after_detection(record, new)
    if record.ai:
        refine_async(record)
    return new


def refine_ai(record):
    """Read the chat with the AI reader and fold its answer into the items, never touching anything a person
    already acted on. The slow model call runs without the lock held. Returns the new keys, [] if the AI could
    not answer (the rules reading stays), or None if newer messages arrived meanwhile (the next pass reads them)."""
    import reader
    import sync

    feed = record.bridge
    with feed.lock:
        messages = list(record.messages)
    changes = reader.read(messages, record.catalogue, ai=True)
    note = reader.LAST_NOTE
    with feed.lock:
        if tuple(m.id for m in record.messages) != tuple(m.id for m in messages):
            return None
        if note:
            if not feed.ai_failed:
                record.job.log.add(datetime.now(), SYSTEM, "ai", "-", f"{note}. The rules reading stays.")
            feed.ai_failed = True
            return []
        feed.ai_failed = False
        new = record.job.reconcile(changes, prefer_incoming=True)
        sync.after_detection(record, new)
        return new


def refine_async(record):
    """Start the AI refinement in the background. At most one runs per group; messages that arrive while it
    runs make it read once more afterwards, so a burst of messages costs one extra read, not one each."""
    feed = record.bridge
    with feed.lock:
        if feed.ai_running:
            feed.ai_dirty = True
            return

        feed.ai_running = True

    def run():
        try:
            while True:
                try:
                    refine_ai(record)
                except Exception:
                    logging.exception("AI refinement failed for %s", record.id)
                with feed.lock:
                    if feed.ai_dirty:
                        feed.ai_dirty = False
                        continue
                    feed.ai_running = False
                    return
        except BaseException:
            with feed.lock:
                feed.ai_running = False
            raise

    threading.Thread(target=run, name="ai-refine", daemon=True).start()


def sync_groups():
    """Merge by stable WhatsApp ID; refresh detection without replacing approvals."""
    import store

    with _poll_lock:
        for record in list(store.JOBS.values()):
            feed = record.bridge
            if feed is None:
                continue
            try:
                _, incoming = fetch_group(feed.group_id, feed.limit)
                # A reset may have removed the job while the bridge was reading.
                if store.JOBS.get(record.id) is not record:
                    continue
                apply_messages(record, incoming)
                feed.error = ""
                feed.checked_at = datetime.now()
            except BridgeError as err:
                feed.error = str(err)
            except Exception:
                feed.error = "Could not sync the group. Retrying automatically."
                logging.exception("WhatsApp group sync failed for %s", record.id)


def start_sync():
    """One background reader per Flask process; continues with the page closed."""
    global _worker
    with _worker_lock:
        if _worker is not None and _worker.is_alive():
            return

        def run():
            tick = threading.Event()
            while not tick.wait(3):
                sync_groups()

        _worker = threading.Thread(target=run, name="whatsapp-sync", daemon=True)
        _worker.start()


def request_pairing_code(phone):
    """Requests an 8-character pairing code to link via phone number instead of QR scanning."""
    clean = "".join(c for c in phone if c.isdigit())
    if len(clean) < 8:
        raise BridgeError("Please enter your country code and phone number (e.g. 60123456789).")
    res = _get(f"/pair?phone={urllib.parse.quote(clean)}", timeout=30)
    return res.get("code")
