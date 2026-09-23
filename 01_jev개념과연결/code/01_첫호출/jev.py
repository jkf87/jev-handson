#!/usr/bin/env python3
"""Ask TypeSafe Jev typed questions and print its answers as JSON.

This is a thin pass-through for ``POST /v1/systemone``. The request body
you give it is the body the API receives; nothing is renamed or wrapped,
so the TypeSafe docs apply verbatim. The script adds only what an agent
cannot do safely on its own:

* credentials are replaced with ``<REDACTED:kind>`` before anything
  leaves the machine, and over-long strings are cut with a marker;
* the API key is resolved from the environment or ``<cwd>/.env`` and
  never printed;
* every failure is reported as JSON on stdout with exit code 0, so the
  caller can fall back to its default behaviour (fail open). Only a
  malformed request exits non-zero, because that is the caller's bug.

Usage::

    python3 jev.py [--model M] [--timeout S] [--dry-run] [-f FILE]

    # request body on stdin
    python3 jev.py <<'EOF'
    {"state": {...}, "questions": {"q": {"type": "noul",
                                        "instructions": "..."}}}
    EOF

Output on success is the API response plus ``latency_ms`` and
``redactions``::

    {"model": "jev-...", "answers": {"q": {"type": "noul",
     "noul": 0.93}}, "usage": {...}, "latency_ms": 251, "redactions": 0}

Output on failure has an ``error`` object and no ``answers``::

    {"error": {"kind": "no_api_key", "message": "..."}, "latency_ms": 0}

Requires Python 3.9+ and the standard library only.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ENV_KEY = "TYPESAFE_API_KEY"
ENV_MODEL = "TYPESAFE_DEFAULT_MODEL"
ENV_BASE_URL = "TYPESAFE_BASE_URL"
DEFAULT_MODEL = "jev-latest"
DEFAULT_BASE_URL = "https://api.typesafe.ai"
DEFAULT_TIMEOUT_S = 8.0
DEFAULT_STRING_CHARS = 2000
DEFAULT_STATE_CHARS = 8000
QUESTION_TYPES = ("noul", "choice", "score")
# HTTP statuses with a specific `error.kind`; everything else is http_error.
_HTTP_KINDS = {401: "unauthorized", 422: "rejected", 429: "rate_limited"}

# ---------------------------------------------------------------------------
# Redaction. Ordered; first match wins per span. Deliberately conservative:
# a false positive costs Jev some context, a false negative ships a secret.
# ---------------------------------------------------------------------------

_SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "pem",
        re.compile(
            r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?"
            r"-----END [A-Z ]*PRIVATE KEY-----",
            re.DOTALL,
        ),
    ),
    (
        "jwt",
        re.compile(
            r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"
            r"\.[A-Za-z0-9_-]{8,}\b"
        ),
    ),
    ("aws", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("github", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b")),
    ("openai", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("slack", re.compile(r"\bxox[abpors]-[A-Za-z0-9-]{10,}\b")),
    ("bearer", re.compile(r"\b[Bb]earer\s+[A-Za-z0-9._~+/=-]{16,}")),
)

# KEY=..., "token": "...", password: ... with a long high-entropy value.
# Only the value is replaced so the field name stays readable.
_ASSIGNMENT = re.compile(
    r"\b([A-Za-z0-9_]*(?:key|token|secret|password|passwd|credential)"
    r"[A-Za-z0-9_]*)([\"']?\s*[:=]\s*[\"']?)([A-Za-z0-9+/_.~-]{16,})",
    re.IGNORECASE,
)
_MARKER = re.compile(r"<REDACTED:[a-z]+>")


class InvalidRequest(ValueError):
    """The request body is not a valid ``/v1/systemone`` request."""


def redact_secrets(text: str, literals: tuple[str, ...] = ()) -> str:
    """Replace recognised credentials in ``text`` with ``<REDACTED:kind>``.

    Args:
        text: Arbitrary text, typically a state field.
        literals: Exact values that must never appear (the API key).

    Returns:
        The text with credentials replaced. Field names in ``KEY=value``
        assignments are kept so the state stays readable.
    """
    out = text
    for literal in literals:
        if len(literal) >= 8:
            out = out.replace(literal, "<REDACTED:key>")
    for kind, pattern in _SECRET_PATTERNS:
        out = pattern.sub(f"<REDACTED:{kind}>", out)
    return _ASSIGNMENT.sub(r"\1\2<REDACTED:assignment>", out)


def truncate(text: str, limit: int) -> str:
    """Cut ``text`` to ``limit`` characters and say how much was dropped."""
    if len(text) <= limit:
        return text
    return f"{text[:limit]}…[{len(text) - limit} chars elided]"


def prepare_state(
    value: Any,
    string_chars: int,
    literals: tuple[str, ...],
) -> tuple[Any, int]:
    """Recursively redact and truncate every string in ``value``.

    Returns:
        The prepared value and how many credentials were replaced. The
        count is taken before truncation so a marker cut in half by the
        string limit is still counted; a non-zero count is hard evidence
        that the original contained a secret, whatever Jev says later.
    """
    if isinstance(value, str):
        redacted = redact_secrets(value, literals)
        found = len(_MARKER.findall(redacted))
        return truncate(redacted, string_chars), found
    if isinstance(value, list):
        items = [prepare_state(v, string_chars, literals) for v in value]
        return [item for item, _ in items], sum(n for _, n in items)
    if isinstance(value, dict):
        total = 0
        out: dict[str, Any] = {}
        for key, item in value.items():
            out[str(key)], found = prepare_state(item, string_chars, literals)
            total += found
        return out, total
    return value, 0


# ---------------------------------------------------------------------------
# Request validation. Mirrors the API contract closely enough that the
# common mistakes (missing no-match option, one-level score, wrong type)
# fail here with a readable message instead of a 422.
# ---------------------------------------------------------------------------


def _validate_question(name: str, question: Any) -> None:
    if not isinstance(question, dict):
        raise InvalidRequest(f'question "{name}" must be an object')
    qtype = question.get("type")
    if qtype not in QUESTION_TYPES:
        raise InvalidRequest(
            f'question "{name}": type must be one of {QUESTION_TYPES}'
        )
    criteria = question.get("criteria")
    if qtype == "choice":
        if not isinstance(criteria, dict) or len(criteria) < 2:
            raise InvalidRequest(
                f'choice "{name}": criteria must be an object with at '
                "least two labels; include a no-match label such as "
                '"ask_user" or "other"'
            )
    elif qtype == "score":
        if not isinstance(criteria, list) or len(criteria) < 2:
            raise InvalidRequest(
                f'score "{name}": criteria must be a list of at least '
                "two level descriptions, lowest first"
            )
    elif criteria is not None and not isinstance(criteria, dict):
        raise InvalidRequest(
            f'noul "{name}": criteria, if given, must be an object with '
            'optional "true" and "false" descriptions'
        )


def validate_request(body: Any) -> dict[str, Any]:
    """Check the shape of a ``/v1/systemone`` body.

    Args:
        body: Parsed JSON from stdin or ``--file``.

    Returns:
        The same body, typed as a dict.

    Raises:
        InvalidRequest: With a message that says what to fix.
    """
    if not isinstance(body, dict):
        raise InvalidRequest("request must be a JSON object")
    if "state" not in body:
        raise InvalidRequest('request needs a "state" field')
    questions = body.get("questions")
    if not isinstance(questions, dict) or not questions:
        raise InvalidRequest(
            '"questions" must be a non-empty object keyed by question name'
        )
    for name, question in questions.items():
        _validate_question(str(name), question)
    model = body.get("model")
    if model is not None and not isinstance(model, str):
        raise InvalidRequest('"model", if given, must be a string')
    return body


# ---------------------------------------------------------------------------
# Key resolution and the HTTP call.
# ---------------------------------------------------------------------------


def _read_dotenv(path: Path, name: str) -> str | None:
    """Minimal ``.env`` reader for ``NAME=value`` lines."""
    if not path.is_file():
        return None
    pattern = re.compile(r"^\s*(?:export\s+)?([A-Z0-9_]+)\s*=\s*(.*?)\s*$")
    for line in path.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line)
        if match and match.group(1) == name:
            return match.group(2).strip("\"'")
    return None


def resolve_api_key() -> str | None:
    """Find the API key: ``TYPESAFE_API_KEY`` env, then ``<cwd>/.env``."""
    from_env = os.environ.get(ENV_KEY, "").strip()
    if from_env:
        return from_env
    return _read_dotenv(Path.cwd() / ".env", ENV_KEY)


def call_system_one(
    body: dict[str, Any],
    api_key: str,
    base_url: str,
    timeout_s: float,
) -> dict[str, Any]:
    """POST ``body`` to ``/v1/systemone`` and return the parsed response.

    Raises:
        urllib.error.HTTPError: For non-2xx responses (status preserved).
        urllib.error.URLError: For connection failures and timeouts.
        ValueError: If the response is not JSON.
    """
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/v1/systemone",
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "jev-judgment-skill/1.0",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout_s) as response:
        parsed = json.loads(response.read().decode("utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError("response is not a JSON object")
    return parsed


def _error(
    kind: str, message: str, started: float, **extra: Any
) -> dict[str, Any]:
    return {
        "error": {"kind": kind, "message": message, **extra},
        "latency_ms": round((time.perf_counter() - started) * 1000),
    }


def _http_error_message(error: urllib.error.HTTPError) -> str:
    try:
        payload = json.loads(error.read().decode("utf-8"))
    except (ValueError, OSError):
        return error.reason if isinstance(error.reason, str) else "HTTP error"
    if isinstance(payload, dict):
        detail = payload.get("error") or payload.get("detail") or payload
        return json.dumps(detail)[:400]
    return json.dumps(payload)[:400]


# ---------------------------------------------------------------------------
# CLI.
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="jev.py",
        description=(
            "Send a /v1/systemone request to TypeSafe Jev and print the "
            "answers. Body is read from stdin unless --file is given."
        ),
    )
    parser.add_argument(
        "-f", "--file", type=Path, help="read the request body from FILE"
    )
    parser.add_argument(
        "--model",
        help=f"override the model (default: ${ENV_MODEL} or {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_S,
        help=f"HTTP timeout in seconds (default {DEFAULT_TIMEOUT_S:g})",
    )
    parser.add_argument(
        "--max-string-chars",
        type=int,
        default=DEFAULT_STRING_CHARS,
        help="cut any string in state longer than this "
        f"(default {DEFAULT_STRING_CHARS})",
    )
    parser.add_argument(
        "--max-state-chars",
        type=int,
        default=DEFAULT_STATE_CHARS,
        help="reject a serialised state larger than this "
        f"(default {DEFAULT_STATE_CHARS})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the redacted body that would be sent; no network, "
        "no key needed",
    )
    return parser.parse_args(argv)


def _read_body(path: Path | None) -> Any:
    raw = path.read_text(encoding="utf-8") if path else sys.stdin.read()
    if not raw.strip():
        raise InvalidRequest("empty request body")
    try:
        return json.loads(raw)
    except ValueError as exc:
        raise InvalidRequest(f"request is not valid JSON: {exc}") from exc


def _emit(payload: dict[str, Any]) -> None:
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns the process exit code."""
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    started = time.perf_counter()

    try:
        body = validate_request(_read_body(args.file))
    except InvalidRequest as exc:
        _emit(_error("invalid_request", str(exc), started))
        return 2

    api_key = resolve_api_key()
    literals = (api_key,) if api_key else ()
    state, redactions = prepare_state(
        body["state"], args.max_string_chars, literals
    )
    serialised = json.dumps(state, ensure_ascii=False)
    if len(serialised) > args.max_state_chars:
        _emit(
            _error(
                "state_too_large",
                f"state serialises to {len(serialised)} chars; limit is "
                f"{args.max_state_chars}. Send only the fields the "
                "question needs.",
                started,
                chars=len(serialised),
            )
        )
        return 2

    model = (
        args.model
        or body.get("model")
        or os.environ.get(ENV_MODEL, "").strip()
        or DEFAULT_MODEL
    )
    outgoing = {"model": model, "state": state, "questions": body["questions"]}

    if args.dry_run:
        _emit({"dry_run": True, "redactions": redactions, "request": outgoing})
        return 0

    if not api_key:
        _emit(
            _error(
                "no_api_key",
                f"set {ENV_KEY} in the environment or in <cwd>/.env "
                "(https://console.typesafe.ai). Proceed without Jev.",
                started,
            )
        )
        return 0

    base_url = os.environ.get(ENV_BASE_URL, "").strip() or DEFAULT_BASE_URL
    try:
        response = call_system_one(outgoing, api_key, base_url, args.timeout)
    except urllib.error.HTTPError as exc:
        _emit(
            _error(
                _HTTP_KINDS.get(exc.code, "http_error"),
                _http_error_message(exc),
                started,
                status=exc.code,
            )
        )
        return 0
    except urllib.error.URLError as exc:
        reason = str(exc.reason)
        kind = "timeout" if "timed out" in reason else "connection"
        _emit(_error(kind, reason, started))
        return 0
    except (TimeoutError, OSError, ValueError) as exc:
        _emit(_error("connection", str(exc), started))
        return 0

    latency_ms = round((time.perf_counter() - started) * 1000)
    _emit({**response, "latency_ms": latency_ms, "redactions": redactions})
    return 0


if __name__ == "__main__":
    sys.exit(main())
