from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from pkm.adapters.youtube import YouTubeError, fetch


def _fake_runner_factory(meta: dict, vtt: str | None):
    """Return a runner that simulates yt-dlp invocations.

    First call: metadata dump → returns CompletedProcess with JSON stdout.
    Second call: subtitle download → writes a .vtt into the `-o` outdir.
    """
    state = {"call": 0}

    def runner(argv: list[str], timeout: int) -> subprocess.CompletedProcess:
        state["call"] += 1
        if "--dump-single-json" in argv:
            return subprocess.CompletedProcess(
                args=argv, returncode=0, stdout=json.dumps(meta), stderr=""
            )
        # subtitle download — write a vtt if provided
        if vtt is not None:
            # extract -o pattern's parent dir
            out_idx = argv.index("-o")
            tmpl = argv[out_idx + 1]
            outdir = Path(tmpl).parent
            outdir.mkdir(parents=True, exist_ok=True)
            (outdir / "video.en.vtt").write_text(vtt, encoding="utf-8")
            return subprocess.CompletedProcess(args=argv, returncode=0, stdout="", stderr="")
        return subprocess.CompletedProcess(args=argv, returncode=1, stdout="", stderr="no subs")

    return runner


def test_fetch_returns_markdown_with_transcript():
    meta = {
        "title": "But what is attention really?",
        "channel": "3Blue1Brown",
        "upload_date": "20240407",
        "duration": 1570,
    }
    vtt = (
        "WEBVTT\nKind: captions\nLanguage: en\n\n"
        "00:00:01.000 --> 00:00:04.000\n"
        "Hello, today we look at attention.\n\n"
        "00:00:04.000 --> 00:00:08.000\n"
        "It is the heart of the transformer.\n"
    )
    md = fetch("https://www.youtube.com/watch?v=zjkBMFhNj_g",
               runner=_fake_runner_factory(meta, vtt))
    assert md.startswith("# But what is attention really?")
    assert "Channel: 3Blue1Brown" in md
    assert "Date: 2024-04-07" in md
    assert "Duration: 26:10" in md
    assert "Hello, today we look at attention." in md
    assert "It is the heart of the transformer." in md


def test_fetch_handles_missing_transcript():
    meta = {"title": "Silent", "channel": "x", "upload_date": "20240101", "duration": 60}
    md = fetch("https://youtu.be/abc", runner=_fake_runner_factory(meta, None))
    assert "_(no transcript available)_" in md


def test_fetch_raises_on_metadata_failure():
    def runner(argv, timeout):
        return subprocess.CompletedProcess(args=argv, returncode=1, stdout="", stderr="oops")

    with pytest.raises(YouTubeError):
        fetch("https://youtu.be/abc", runner=runner)


def test_vtt_dedupes_repeated_cues():
    meta = {"title": "x", "channel": "y", "upload_date": "20240101", "duration": 10}
    # Auto-subs often repeat the same line across overlapping cues.
    vtt = (
        "WEBVTT\n\n"
        "00:00:01.000 --> 00:00:02.000\n<c>hello world</c>\n\n"
        "00:00:01.500 --> 00:00:02.500\nhello world\n\n"
        "00:00:03.000 --> 00:00:04.000\nnext line\n"
    )
    md = fetch("https://youtu.be/abc", runner=_fake_runner_factory(meta, vtt))
    # "hello world" should appear exactly once in transcript area
    assert md.count("hello world") == 1
    assert "next line" in md
