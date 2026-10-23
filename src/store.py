"""In-memory job store for the prototype. Demo jobs load from data/ and can be reset at any time.
A real deployment would keep this in Orbyte's project records instead."""
import json
import re
from dataclasses import dataclass, field
from datetime import datetime

import sync
from catalogue import DATA, Catalogue
from chat_import import parse_chat
from reader import read as extract
from workflow import Actor, Job

DEMO_JOBS = [  # (job id, chat file, quote file)
    ("annual-dinner", "dinner_client.txt", "q_dinner.json"),
    ("product-launch", "launch_client.txt", "q_launch.json"),
    ("wedding-dinner", "wedding_client.txt", "q_wedding.json"),
    ("cafe-fit-out", "cafe_client.txt", "q_cafe.json"),
]

# People who use the web app. The client only opens a link from WhatsApp; finance downloads the CSV.
ROLE_LABELS = {"pm": "Project manager", "owner": "Owner", "client": "Client (WhatsApp link)"}


@dataclass
class JobRecord:
    id: str
    chat_name: str
    messages: list
    catalogue: Catalogue
    job: Job
    imported_at: datetime
    versions: list = field(default_factory=list)   # sync.QuoteVersion, v1 = signed quote
    outbox: list = field(default_factory=list)     # sync.Outgoing, messages to the group or a person
    live: object = None                            # webhook.LiveFeed when fed message by message

    @property
    def title(self):
        return self.catalogue.quote["job"]

    @property
    def team(self):
        """Named people for each role, from the company directory (Orbyte's Directory, simulated)."""
        q = self.catalogue.quote
        people = team_directory().get(q["company"], {})
        return {"pm": people.get("pm", "Project manager"), "owner": people.get("owner", "Owner"),
                "finance": people.get("finance", "Finance"), "client": q["client"]}

    def actor(self, role):
        return Actor(self.team[role], role)


def team_directory():
    return json.loads((DATA / "team.json").read_text(encoding="utf-8"))["companies"]


JOBS: dict[str, JobRecord] = {}


def build(job_id, chat_text, chat_name, quote_file):
    return build_from_messages(job_id, parse_chat(chat_text), chat_name, quote_file)


def build_from_messages(job_id, messages, chat_name, quote_file):
    """Same as build(), for messages already read, e.g. live from a WhatsApp group."""
    catalogue = Catalogue.load(quote_file)
    now = datetime.now()
    record = JobRecord(job_id, chat_name, messages, catalogue, Job(extract(messages, catalogue), now=now), now)
    sync.start(record)
    JOBS[job_id] = record
    return record


GROUPS: dict[str, str] = {}  # WhatsApp group id -> job id


def build_live(job_id, chat_file, quote_file, seed=3):
    """A job fed message by message through the webhook, as the official API would. The demo
    script is a synthetic chat: the first `seed` messages have arrived, the rest wait in order."""
    import webhook

    script = [m for m in parse_chat((DATA / "chats" / chat_file).read_text(encoding="utf-8")) if m.sender]
    record = build_from_messages(job_id, [], "WhatsApp group, live (simulated)", quote_file)
    group_id = f"demo-{job_id}@g.us"
    record.live = webhook.LiveFeed(group_id, script=[webhook.payload_for(group_id, m, i) for i, m in enumerate(script)])
    GROUPS[group_id] = job_id
    for _ in range(seed):
        play_next(record)
    return record


def play_next(record):
    """Demo: deliver the next scripted message through the same path as a real webhook."""
    if record.live and record.live.script:
        receive(record.live.script.pop(0))


def receive(payload):
    """Route an incoming webhook payload to the job its WhatsApp group belongs to."""
    import webhook

    for rec in webhook.records_from_payload(payload):
        record = JOBS.get(GROUPS.get(rec["group_id"], ""))
        if record is not None and record.live is not None:
            webhook.ingest(record, [rec])


def reset_demo():
    JOBS.clear()
    GROUPS.clear()
    build_live("annual-dinner-live", "dinner_client.txt", "q_dinner.json")
    for job_id, chat, quote in DEMO_JOBS:
        build(job_id, (DATA / "chats" / chat).read_text(encoding="utf-8"), chat, quote)


def quote_files():
    return sorted(p.name for p in (DATA / "quotes").glob("*.json"))


def quote_title(quote_file):
    return json.loads((DATA / "quotes" / quote_file).read_text(encoding="utf-8"))["job"]


def new_job_id(name):
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "job"
    job_id, n = base, 2
    while job_id in JOBS:
        job_id, n = f"{base}-{n}", n + 1
    return job_id
