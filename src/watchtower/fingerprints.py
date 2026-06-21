from __future__ import annotations

import hashlib
import re

_ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_UUID = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-"
    r"[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}\b"
)
_HEX = re.compile(r"\b0x[0-9a-fA-F]+\b")
_PATH_LINE = re.compile(r"(?P<path>(?:[A-Za-z]:)?[^\s:]+\.[A-Za-z0-9]+):\d+(?::\d+)?")
_LINE_NUMBER = re.compile(r"\b(?:line|column|col)\s+\d+\b", re.IGNORECASE)
_VOLATILE_NUMBER = re.compile(r"\b\d{5,}\b")
_WHITESPACE = re.compile(r"\s+")


def normalize_failure_text(value: str) -> str:
    text = _ANSI.sub("", value)
    text = _UUID.sub("<uuid>", text)
    text = _HEX.sub("<hex>", text)
    text = _PATH_LINE.sub(lambda match: f"{match.group('path')}:<line>", text)
    text = _LINE_NUMBER.sub("line <n>", text)
    text = _VOLATILE_NUMBER.sub("<n>", text)
    return _WHITESPACE.sub(" ", text).strip().lower()[:4000]


def failure_fingerprint(*, tool_name: str, verification_key: str | None, error: str) -> str:
    material = "\n".join(
        [
            tool_name.strip().lower(),
            (verification_key or "").strip().lower(),
            normalize_failure_text(error),
        ]
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]
    return f"failure_{digest}"
