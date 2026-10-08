"""Conservative estimates, not a claim of tokenizer-exact usage."""
import json
import math


def compact_json(value):
    return json.dumps(value, ensure_ascii=False, default=str, separators=(',', ':'))


def estimate_tokens(value):
    text = value if isinstance(value, str) else compact_json(value)
    # UTF-8 bytes also account for CJK and other non-ASCII business documents.
    # Include framing margin; Groq's actual usage/limit headers remain authoritative.
    return math.ceil(len(text.encode('utf-8')) / 3) + 32
