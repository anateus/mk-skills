#!/usr/bin/env python3
"""Create a compact, redacted index of Claude Code JSONL debugging sessions."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


SKIP_PREFIXES = (
    "<local-command-caveat>",
    "<command-name>",
    "<local-command-stdout>",
    "<system-reminder>",
    "<task-notification>",
    "<teammate-message>",
    "This session is being continued from a previous conversation",
)
CORRECTION_RE = re.compile(
    r"\b(correction|corrected|retract|retracted|revision|revised|walk back|"
    r"scratch that|misread|mistake|overturned|forced me to)\b",
    re.IGNORECASE,
)
SECRET_PATTERNS = (
    re.compile(r"(?i)(authorization\s*:\s*bearer\s+)[^\s,;]+"),
    re.compile(r"(?i)\b((?:[A-Z][A-Z0-9_]*_)?(?:TOKEN|SECRET|PASSWORD|API_KEY)\s*=\s*)[^\s,;]+"),
    re.compile(r"(?i)\b((?:password|secret|api[_ -]?key|access[_ -]?token)\s*[:=]\s*)[^\s,;]+"),
)


def redact(text: str) -> str:
    for pattern in SECRET_PATTERNS:
        text = pattern.sub(lambda match: f"{match.group(1)}<redacted>", text)
    return text


def compact(text: str, limit: int = 700) -> str:
    text = redact(re.sub(r"\s+", " ", text).strip())
    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()} … [truncated {len(text) - limit} chars]"


def text_blocks(content: Any) -> Iterable[str]:
    if isinstance(content, str):
        yield content
    elif isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text")
                if isinstance(text, str):
                    yield text


def session_files(paths: list[Path], include_subagents: bool) -> list[Path]:
    found: set[Path] = set()
    for path in paths:
        if path.is_dir():
            candidates = path.glob("*.jsonl")
        else:
            candidates = [path]
        for candidate in candidates:
            if candidate.is_file() and candidate.suffix == ".jsonl":
                found.add(candidate.resolve())
                if include_subagents:
                    subagents = candidate.with_suffix("") / "subagents"
                    if subagents.is_dir():
                        found.update(item.resolve() for item in subagents.glob("*.jsonl"))
    return sorted(found)


def load_events(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    seen_uuids: set[str] = set()
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            try:
                value = json.loads(line)
            except json.JSONDecodeError as error:
                print(f"warning: {path}:{number}: {error}", file=sys.stderr)
                continue
            if isinstance(value, dict):
                uuid = value.get("uuid")
                if isinstance(uuid, str):
                    if uuid in seen_uuids:
                        continue
                    seen_uuids.add(uuid)
                events.append(value)
    return events


def render(path: Path, events: list[dict[str, Any]]) -> str:
    tool_counts: Counter[str] = Counter()
    command_descriptions: Counter[str] = Counter()
    agents: Counter[str] = Counter()
    requests: list[tuple[str, str]] = []
    corrections: list[tuple[str, str]] = []
    timestamps = [event.get("timestamp") for event in events if event.get("timestamp")]
    cwd = next((event.get("cwd") for event in events if event.get("cwd")), "unknown")

    for event in events:
        timestamp = str(event.get("timestamp") or "unknown-time")
        message = event.get("message")
        if not isinstance(message, dict):
            continue
        role = message.get("role")
        content = message.get("content")
        if event.get("type") == "user" and role == "user":
            for text in text_blocks(content):
                stripped = text.lstrip()
                if stripped and not stripped.startswith(SKIP_PREFIXES):
                    requests.append((timestamp, compact(text)))
        if event.get("type") != "assistant" or role != "assistant" or not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text" and isinstance(block.get("text"), str):
                if CORRECTION_RE.search(block["text"]):
                    corrections.append((timestamp, compact(block["text"])))
            if block.get("type") != "tool_use":
                continue
            name = str(block.get("name") or "unknown")
            tool_counts[name] += 1
            data = block.get("input")
            if not isinstance(data, dict):
                continue
            if name == "Bash" and data.get("description"):
                command_descriptions[compact(str(data["description"]), 240)] += 1
            if name in {"Agent", "Task"} and data.get("description"):
                agents[compact(str(data["description"]), 240)] += 1

    lines = [
        f"## {path.name}",
        "",
        f"- Path: `{path}`",
        f"- Working directory: `{cwd}`",
        f"- Time range: {min(timestamps) if timestamps else 'unknown'} to {max(timestamps) if timestamps else 'unknown'}",
        f"- Events: {len(events)}",
        "",
        "### Direct user requests",
        "",
    ]
    lines.extend(f"- `{timestamp}` — {text}" for timestamp, text in requests)
    if not requests:
        lines.append("- None found.")

    lines.extend(["", "### Tool usage", ""])
    lines.extend(f"- `{name}`: {count}" for name, count in tool_counts.most_common())
    if not tool_counts:
        lines.append("- None found.")

    lines.extend(["", "### Delegated investigations", ""])
    lines.extend(f"- {description} ({count}x)" for description, count in agents.most_common())
    if not agents:
        lines.append("- None found.")

    lines.extend(["", "### Shell command intents", ""])
    lines.extend(f"- {description} ({count}x)" for description, count in command_descriptions.most_common())
    if not command_descriptions:
        lines.append("- None found.")

    lines.extend(["", "### Candidate correction points", ""])
    lines.extend(f"- `{timestamp}` — {text}" for timestamp, text in corrections)
    if not corrections:
        lines.append("- None found.")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path, help="Claude session JSONL files or project directories")
    parser.add_argument("--include-subagents", action="store_true", help="include subagent JSONL under selected sessions")
    args = parser.parse_args()
    files = session_files(args.paths, args.include_subagents)
    if not files:
        parser.error("no JSONL session files found")
    print("# Claude session retrospective index\n")
    print("Generated without raw shell bodies or tool results. Verify important claims in the source transcript.\n")
    for index, path in enumerate(files):
        if index:
            print("\n")
        print(render(path, load_events(path)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
