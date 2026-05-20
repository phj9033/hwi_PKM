"""YouTube transcript + metadata via `yt-dlp`.

Shells out to the `yt-dlp` binary (installed via `[adapters]` extra). We
ask for auto-generated subtitles in en/ko (whichever is available), skip
the actual video download, and parse the `.vtt` to strip timestamps.

The function returns a markdown document the caller can pipe into
`pkm capture create`. Failures raise YouTubeError so the slash template
can either fall back to Jina or skip with a warning.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from pkm.errors import PKMError


class YouTubeError(PKMError):
    code = "YOUTUBE_ERROR"


_YTDLP_TIMEOUT = 60  # seconds — auto-sub download for a single video


def fetch(url: str, *, runner=None) -> str:
    """Return a markdown document with title, channel, date, and transcript.

    `runner` is an injectable callable mimicking subprocess.run, used in
    tests. Production callers leave it None.
    """
    runner = runner or _default_runner
    if shutil.which("yt-dlp") is None and runner is _default_runner:
        raise YouTubeError(
            "yt-dlp not found on PATH",
            hint="Install with: uv pip install '.[adapters]'  (or: pipx install yt-dlp)",
        )

    with TemporaryDirectory() as td:
        outdir = Path(td)
        meta = _fetch_metadata(url, runner)
        transcript = _fetch_transcript(url, outdir, runner)

    title = meta.get("title") or "(no title)"
    channel = meta.get("channel") or meta.get("uploader") or "?"
    upload_date = _format_date(meta.get("upload_date"))
    duration = _format_duration(meta.get("duration"))

    parts = [
        f"# {title}",
        f"> Channel: {channel} · Date: {upload_date} · Duration: {duration}",
        "",
    ]
    if transcript:
        parts.append(transcript)
    else:
        parts.append("_(no transcript available)_")
    return "\n".join(parts).strip() + "\n"


def _default_runner(argv: list[str], timeout: int) -> subprocess.CompletedProcess:
    return subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)


def _fetch_metadata(url: str, runner) -> dict:
    argv = ["yt-dlp", "--dump-single-json", "--no-warnings", "--skip-download", url]
    proc = runner(argv, _YTDLP_TIMEOUT)
    if proc.returncode != 0:
        raise YouTubeError(f"yt-dlp metadata failed: {proc.stderr.strip()[:200]}")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise YouTubeError(f"yt-dlp metadata not JSON: {e}") from e


def _fetch_transcript(url: str, outdir: Path, runner) -> str:
    argv = [
        "yt-dlp",
        "--write-auto-sub",
        "--sub-lang", "en,ko",
        "--sub-format", "vtt",
        "--skip-download",
        "--no-warnings",
        "-o", str(outdir / "%(id)s.%(ext)s"),
        url,
    ]
    proc = runner(argv, _YTDLP_TIMEOUT)
    if proc.returncode != 0:
        return ""
    vtts = sorted(outdir.glob("*.vtt"))
    if not vtts:
        return ""
    return _vtt_to_text(vtts[0].read_text(encoding="utf-8", errors="ignore"))


_TIMESTAMP_RE = re.compile(r"^\d{2}:\d{2}:\d{2}\.\d{3}\s+-->\s+\d{2}:\d{2}:\d{2}\.\d{3}")
_TAG_RE = re.compile(r"<[^>]+>")


def _vtt_to_text(vtt: str) -> str:
    """Strip WebVTT cue headers, tags, duplicates → plain paragraph text."""
    out_lines: list[str] = []
    seen: set[str] = set()
    for raw in vtt.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line == "WEBVTT" or line.startswith("Kind:") or line.startswith("Language:"):
            continue
        if _TIMESTAMP_RE.match(line):
            continue
        if "-->" in line:
            continue
        clean = _TAG_RE.sub("", line).strip()
        if not clean or clean in seen:
            continue
        seen.add(clean)
        out_lines.append(clean)
    return "\n".join(out_lines)


def _format_date(yyyymmdd: str | None) -> str:
    if not yyyymmdd or len(yyyymmdd) != 8:
        return "?"
    return f"{yyyymmdd[:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:]}"


def _format_duration(seconds) -> str:
    if not isinstance(seconds, (int, float)):
        return "?"
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"
