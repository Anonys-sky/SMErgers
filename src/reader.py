"""Chooses which reader turns a chat into changes, so the rest of the app never cares.

    SMERGERS_READER=rules   (default) the offline rules reader
    SMERGERS_READER=llm     the AI reader; if the model is unreachable or answers badly,
                            the rules reader runs instead and the reason is kept in LAST_NOTE
"""
import os
import json

import llm_extractor
import rules_extractor

LAST_NOTE = ""
_cache = {}


def read(messages, catalogue, ai=None):
    """Changes for these messages. ai=True asks for the AI reader, ai=False for the rules; None follows
    SMERGERS_READER. Repeated calls on the same chat reuse the model's answer."""
    global LAST_NOTE
    LAST_NOTE = ""
    if ai is None:
        ai = os.environ.get("SMERGERS_READER", "rules") == "llm"
    if not ai:
        return rules_extractor.extract(messages, catalogue)
    key = (tuple(m.id for m in messages), json.dumps(catalogue.quote, sort_keys=True))
    if key not in _cache:
        try:
            _cache[key] = llm_extractor.extract(messages, catalogue)
            LAST_NOTE = ""
        except llm_extractor.ReaderError as exc:
            LAST_NOTE = f"AI reader unavailable, rules used instead ({exc})"
            return rules_extractor.extract(messages, catalogue)
    return [_copy(c) for c in _cache[key]]


def _copy(change):
    from dataclasses import replace
    return replace(change, evidence_ids=list(change.evidence_ids))
