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


_worker = None
_worker_lock = threading.Lock()
_poll_lock = threading.Lock()


def sync_groups():
    """Merge by stable WhatsApp ID; refresh detection without replacing approvals."""
    import store
    import sync

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
                with feed.lock:
                    merged = {m.id: m for m in record.messages}
                    merged.update((m.id, m) for m in incoming)
                    messages = [replace(m, seq=i) for i, m in enumerate(
                        sorted(merged.values(), key=lambda m: m.sent_at), 1)]
                    if messages != record.messages:
                        changes = store.extract(messages, record.catalogue, ai=record.ai)
                        new = record.job.refresh(changes)
                        record.messages = messages
                        sync.after_detection(record, new)
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
