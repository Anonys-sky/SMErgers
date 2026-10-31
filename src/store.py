"""In-memory job store for the prototype. Demo jobs load from data/ and can be reset at any time.
A real deployment would keep this in Orbyte's project records instead."""
import json
import re
from dataclasses import dataclass, field
from datetime import datetime

import sync
from catalogue import DATA, Catalogue
from chat_import import parse_chat
import reader
from reader import read as extract
from workflow import Actor, Job

DEMO_JOBS = [  # (job id, chat file, quote file)
    ("annual-dinner", "dinner_client.txt", "q_dinner.json"),
    ("product-launch", "launch_client.txt", "q_launch.json"),
    ("wedding-dinner", "wedding_client.txt", "q_wedding.json"),
    ("cafe-fit-out", "cafe_client.txt", "q_cafe.json"),
]

# Demo workspaces. The client opens a link from WhatsApp; finance reads bills and exports the CSV.
ROLE_LABELS = {"pm": "Project Manager", "owner": "Project Director", "client": "Client", "finance": "Finance"}


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
    ai: bool = False                               # read by the AI reader instead of the rules
    bridge: object = None                         # whatsapp_bridge.GroupSync for a linked group

    @property
    def title(self):
        return self.catalogue.quote["job"]

    @property
    def team(self):
        """Named people for each role, from the company directory (Orbyte's Directory, simulated)."""
        q = self.catalogue.quote
        people = q.get("team") or team_directory().get(q["company"], {})
        return {"pm": people.get("pm", "Project manager"), "owner": people.get("owner", "Project director"),
                "finance": people.get("finance", "Finance"), "client": q["client"]}

    def actor(self, role):
        return Actor(self.team[role], role)


def team_directory():
    return json.loads((DATA / "team.json").read_text(encoding="utf-8"))["companies"]


JOBS: dict[str, JobRecord] = {}


def build(job_id, chat_text, chat_name, quote_file, ai=False):
    return build_from_messages(job_id, parse_chat(chat_text), chat_name, quote_file, ai)


def build_from_messages(job_id, messages, chat_name, quote_file, ai=False):
    """Same as build(), for messages already read, e.g. live from a WhatsApp group."""
    catalogue = Catalogue.load(quote_file)
    return build_with_catalogue(job_id, messages, chat_name, catalogue, ai)


def build_with_catalogue(job_id, messages, chat_name, catalogue, ai=False):
    """Publish a complete record only after extraction and version initialization succeed."""
    now = datetime.now()
    changes = extract(messages, catalogue, ai=ai)
    record = JobRecord(job_id, chat_name, messages, catalogue,
                       Job(changes, policy=catalogue.quote.get("policy"), now=now, catalogue=catalogue), now,
                       ai=ai and not reader.LAST_NOTE)
    sync.start(record)
    JOBS[job_id] = record
    return record


GROUPS: dict[str, str] = {}  # WhatsApp group id -> job id


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
