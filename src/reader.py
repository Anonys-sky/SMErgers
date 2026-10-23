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


def read(messages, catalogue):
    """Changes for these messages. Repeated calls on the same chat reuse the model's answer."""
    global LAST_NOTE
    if os.environ.get("SMERGERS_READER", "rules") != "llm":
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
