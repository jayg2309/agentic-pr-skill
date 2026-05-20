"""
Transcript Helper — Shared module for Cursor AI agent skills.

Reads Cursor agent chat transcripts, scores them for relevance against
a git diff, and returns the top-N most relevant excerpts for use as
context in commit message and PR description generation.

Usage (CLI — pipe diff from stdin):
    git diff --staged | python3 transcript_helper.py [--top-n 3]

Usage (CLI — pass diff as a file):
    python3 transcript_helper.py --diff-file /tmp/my.diff --top-n 5

Usage (as importable module):
    from transcript_helper import score_transcripts
    context = score_transcripts(diff_text, top_n=3)

Only stdlib dependencies — no pip packages required.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

_MAX_EXCERPT_WORDS = 300
_RECENCY_THRESHOLD_SECS = 86_400  # 24 hours

_WEIGHT_RECENCY = 0.4
_WEIGHT_KEYWORD = 0.6


# ---------------------------------------------------------------------------
# Transcript discovery
# ---------------------------------------------------------------------------

def _find_transcript_dirs() -> list[Path]:
    """Auto-discover Cursor agent transcript directories.

    Checks three locations in priority order:
      1. ~/.cursor/projects/*/agent-transcripts/  (project-scoped logs)
      2. <cwd>/.cursor/logs/                      (workspace-level logs)
      3. ~/.cursor/logs/                           (user-level logs)
    """
    candidates: list[Path] = []

    cursor_projects = Path.home() / ".cursor" / "projects"
    if cursor_projects.is_dir():
        for project_dir in cursor_projects.iterdir():
            agent_dir = project_dir / "agent-transcripts"
            if agent_dir.is_dir():
                candidates.append(agent_dir)

    workspace_logs = Path.cwd() / ".cursor" / "logs"
    if workspace_logs.is_dir():
        candidates.append(workspace_logs)

    user_logs = Path.home() / ".cursor" / "logs"
    if user_logs.is_dir() and user_logs not in candidates:
        candidates.append(user_logs)

    return candidates


def _collect_transcript_files(dirs: list[Path]) -> list[tuple[Path, float]]:
    """Collect .jsonl and .txt transcript files with modification times.

    Handles both flat layouts (files directly in the directory) and
    UUID-subdirectory layouts (each chat in its own folder).  Skips
    anything under a ``subagents/`` subtree.
    """
    files: list[tuple[Path, float]] = []
    seen: set[str] = set()

    for d in dirs:
        for pattern in ("*.jsonl", "*.txt", "*/*.jsonl"):
            for f in d.glob(pattern):
                resolved = str(f.resolve())
                if not f.is_file() or resolved in seen:
                    continue
                if "subagents" in f.parts:
                    continue
                seen.add(resolved)
                try:
                    mtime = f.stat().st_mtime
                except OSError:
                    mtime = 0.0
                files.append((f, mtime))

    files.sort(key=lambda x: x[1], reverse=True)
    return files


# ---------------------------------------------------------------------------
# Transcript reading
# ---------------------------------------------------------------------------

def _read_transcript_content(path: Path) -> str:
    """Read a transcript file and extract its text content.

    For JSONL files, parses each line as a message object and pulls out
    ``text``-type content blocks.  For plain-text files, returns the raw
    content as-is.
    """
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""

    if path.suffix == ".jsonl":
        parts: list[str] = []
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            content_blocks = obj.get("message", {}).get("content", [])
            for block in content_blocks:
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(block.get("text", ""))
        return "\n".join(parts)

    return raw


# ---------------------------------------------------------------------------
# Diff token extraction
# ---------------------------------------------------------------------------

def _extract_diff_tokens(diff_text: str) -> list[str]:
    """Pull meaningful identifiers out of a unified diff.

    Extracts file paths (full and basename), class names, function /
    method names, constants, interfaces, and type aliases — anything
    longer than 4 characters that can serve as a keyword signal.
    """
    tokens: list[str] = []
    seen: set[str] = set()

    def _add(token: str) -> None:
        if token and token not in seen:
            seen.add(token)
            tokens.append(token)

    for line in diff_text.splitlines():
        # File paths from diff headers
        m = re.match(r"^(?:---|\+\+\+) [ab]/(.+)$", line)
        if m:
            path = m.group(1)
            if path != "/dev/null":
                _add(path)
                _add(os.path.basename(path))
            continue

        # Only scan added / removed code lines
        if line.startswith("+++") or line.startswith("---"):
            continue
        if not (line.startswith("+") or line.startswith("-")):
            continue

        content = line[1:]
        for pattern in (
            r"\bclass\s+(\w+)",
            r"\bdef\s+(\w+)",
            r"\bfunction\s+(\w+)",
            r"\bconst\s+(\w+)",
            r"\binterface\s+(\w+)",
            r"\btype\s+(\w+)\s*=",
        ):
            for match in re.finditer(pattern, content):
                name = match.group(1)
                if len(name) > 4:
                    _add(name)

    return tokens


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _truncate_to_words(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + " [...]"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def score_transcripts(diff_text: str, top_n: int = 3) -> str:
    """Score agent chat transcripts for relevance to a git diff.

    Reads all discoverable Cursor agent transcripts, scores each one
    against the provided diff using keyword overlap and recency, and
    returns the top *top_n* excerpts as a formatted string ready for
    injection into a commit-message or PR-description prompt.

    Scoring formula per transcript file::

        recency_score = 1.0  if modified within last 24 h, else 0.3
        keyword_score = matched_tokens / total_tokens
        final_score   = (recency_score × 0.4) + (keyword_score × 0.6)

    Returns an empty string when no transcripts are found or none score
    above zero.
    """
    dirs = _find_transcript_dirs()
    if not dirs:
        return ""

    files = _collect_transcript_files(dirs)
    if not files:
        return ""

    tokens = _extract_diff_tokens(diff_text)
    if not tokens:
        return ""

    now = datetime.now(tz=timezone.utc).timestamp()
    scored: list[tuple[float, Path, str]] = []

    for path, mtime in files:
        content = _read_transcript_content(path)
        if not content.strip():
            continue

        age_secs = now - mtime
        recency_score = 1.0 if age_secs <= _RECENCY_THRESHOLD_SECS else 0.3

        content_lower = content.lower()
        matched = sum(1 for t in tokens if t.lower() in content_lower)
        keyword_score = matched / len(tokens)

        final_score = (_WEIGHT_RECENCY * recency_score) + (
            _WEIGHT_KEYWORD * keyword_score
        )

        if final_score > 0.0:
            excerpt = _truncate_to_words(content, _MAX_EXCERPT_WORDS)
            scored.append((final_score, path, excerpt))

    if not scored:
        return ""

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:top_n]

    parts: list[str] = []
    for score, path, excerpt in top:
        header = f"--- Transcript: {path.name} (score: {score:.2f}) ---"
        parts.append(f"{header}\n{excerpt}")

    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Score Cursor agent transcripts against a git diff"
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=3,
        help="Number of top-scoring transcripts to return (default: 3)",
    )
    parser.add_argument(
        "--diff-file",
        type=str,
        default=None,
        help="Path to a file containing the diff (reads stdin if omitted)",
    )
    args = parser.parse_args()

    if args.diff_file:
        diff_text = Path(args.diff_file).read_text(
            encoding="utf-8", errors="replace"
        )
    else:
        diff_text = sys.stdin.read()

    result = score_transcripts(diff_text, top_n=args.top_n)
    if result:
        print(result)
    else:
        print("(no relevant transcripts found)")
