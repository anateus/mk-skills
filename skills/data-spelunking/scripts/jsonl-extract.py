#!/usr/bin/env python3
"""Bounded extractor for large NDJSON/JSONL, Claude Code session transcripts,
or plain text.

Prints matching content as short, line-referenced snippets so a *finding*
lands in context instead of a multi-megabyte corpus. Reading a whole session
transcript (2-16 MB) or grepping raw JSON into context is what makes agents
thrash and abort; this is the safe alternative.

Usage:
  jsonl-extract.py FILE... --match REGEX
                   [--mode auto|ndjson|transcript|text]
                   [--field a.b.c] [--max-chars N] [--no-filter]
                   [-i] [--out PATH]

Modes:
  transcript  Claude Code / Anthropic message JSONL. Pulls human-readable text
              from message.content (text blocks, tool_use inputs, tool_result
              text), tags each hit with line + role, and drops known
              boilerplate (agent listings, system reminders, task notes).
  ndjson      Generic one-JSON-object-per-line. With --field, projects that
              dot-path; otherwise matches against the compact JSON.
  text        Plain text: grep-with-line-numbers + truncation.
  auto        transcript if lines look like CC messages, ndjson if they parse
              as JSON, else text. (default)

Stdlib only. Malformed lines are tolerated, not fatal.
"""
from __future__ import annotations

import argparse
import json
import re
import sys

BOILERPLATE = re.compile(
    r"agent_listing|FleetView|task-notification fires each time"
    r"|<system-reminder>|had no active task; resumed",
    re.I,
)


def get_path(obj, path):
    cur = obj
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def transcript_text(msg):
    """Human-readable text from an Anthropic/CC message object."""
    out = []
    if not isinstance(msg, dict):
        return out
    content = msg.get("content")
    if isinstance(content, str):
        out.append(content)
    elif isinstance(content, list):
        for b in content:
            if not isinstance(b, dict):
                continue
            t = b.get("type")
            if t == "text" and b.get("text"):
                out.append(b["text"])
            elif t == "tool_use":
                out.append(
                    f"[tool_use {b.get('name', '')}] "
                    + json.dumps(b.get("input", {}), default=str)[:1500]
                )
            elif t == "tool_result":
                c = b.get("content")
                if isinstance(c, str):
                    out.append(c)
                elif isinstance(c, list):
                    for x in c:
                        if isinstance(x, dict) and x.get("type") == "text":
                            out.append(x.get("text", ""))
    return out


def decide_mode(path):
    """Sniff the first lines. Transcript wins if ANY early line looks like a
    Claude Code / Anthropic message — these files often open with a summary,
    attachment, or hook line that is not itself a message."""
    seen_json = False
    try:
        with open(path, "r", errors="replace") as fh:
            for k, line in enumerate(fh):
                if k >= 50:
                    break
                if not line.strip():
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                seen_json = True
                if isinstance(obj, dict) and (
                    "message" in obj
                    or obj.get("type") in ("user", "assistant")
                    or "role" in obj
                ):
                    return "transcript"
    except OSError:
        return "text"
    return "ndjson" if seen_json else "text"


def emit(sink, tag, line_no, role, text, max_chars):
    snip = " ".join(text.split())
    if len(snip) > max_chars:
        snip = snip[:max_chars] + "…"
    prefix = f"[{tag} L{line_no} {role}]" if role else f"[{tag} L{line_no}]"
    sink.write(f"{prefix} {snip}\n")


def main():
    ap = argparse.ArgumentParser(
        description="Bounded extractor for big JSONL/transcripts/text."
    )
    ap.add_argument("files", nargs="+")
    ap.add_argument("--match", required=True, help="regex to filter records")
    ap.add_argument(
        "--mode", default="auto",
        choices=["auto", "ndjson", "transcript", "text"],
    )
    ap.add_argument("--field", help="dot-path to project (ndjson mode)")
    ap.add_argument("--max-chars", type=int, default=400)
    ap.add_argument("--no-filter", action="store_true", help="keep boilerplate")
    ap.add_argument("-i", "--ignore-case", action="store_true")
    ap.add_argument("--out", help="write here instead of stdout")
    args = ap.parse_args()

    pat = re.compile(args.match, re.I if args.ignore_case else 0)
    sink = open(args.out, "w") if args.out else sys.stdout
    n = 0
    try:
        for path in args.files:
            mode = decide_mode(path) if args.mode == "auto" else args.mode
            tag = path.split("/")[-1][:8]
            with open(path, "r", errors="replace") as fh:
                for i, line in enumerate(fh, 1):
                    if not line.strip():
                        continue
                    obj = None
                    if mode != "text":
                        try:
                            obj = json.loads(line)
                        except Exception:
                            obj = None

                    if mode == "transcript" and obj is not None:
                        msg = obj.get("message", obj) if isinstance(obj, dict) else obj
                        role = (
                            (msg.get("role") if isinstance(msg, dict) else None)
                            or (obj.get("type", "") if isinstance(obj, dict) else "")
                        )
                        paras = []
                        for txt in transcript_text(msg):
                            paras.extend(re.split(r"\n{1,}", txt))
                        for p in paras:
                            p = p.strip()
                            if not p or not pat.search(p):
                                continue
                            if not args.no_filter and BOILERPLATE.search(p):
                                continue
                            emit(sink, tag, i, role, p, args.max_chars)
                            n += 1
                    elif mode == "ndjson" and obj is not None:
                        proj = get_path(obj, args.field) if args.field else obj
                        if proj is None:
                            continue
                        s = proj if isinstance(proj, str) else json.dumps(proj, default=str)
                        if not pat.search(s):
                            continue
                        emit(sink, tag, i, "", s, args.max_chars)
                        n += 1
                    else:  # text, or a line that would not parse
                        if not pat.search(line):
                            continue
                        emit(sink, tag, i, "", line.rstrip("\n"), args.max_chars)
                        n += 1
        sink.write(f"\n== {n} match(es) ==\n")
    finally:
        if args.out:
            sink.close()
    if args.out:
        print(f"wrote {n} match(es) to {args.out}")


if __name__ == "__main__":
    main()
