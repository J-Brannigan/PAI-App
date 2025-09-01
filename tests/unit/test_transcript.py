# tests/unit/test_transcript.py

from __future__ import annotations
import sys, json
from pathlib import Path

# Make "src" importable
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from pai.storage.transcript import Transcript


def test_in_memory_transcript_messages_order():
    t = Transcript(system_prompt="sys", root_dir=None)
    t.append_message("user", "hi")
    t.append_message("assistant", "ok")
    msgs = t.messages
    assert msgs[0] == {"role": "system", "content": "sys"}
    assert msgs[1] == {"role": "user", "content": "hi"}
    assert msgs[2] == {"role": "assistant", "content": "ok"}


def test_file_backed_writes_and_resume(tmp_path: Path):
    t = Transcript(system_prompt="sys", root_dir=tmp_path)
    sid = t.session_id
    t.append_message("user", "hello")
    t.append_message("assistant", "world")

    # File exists with header + system + two messages
    path = tmp_path / f"{sid}.jsonl"
    assert path.exists()
    lines = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]
    assert lines[0]["type"] == "header"
    assert lines[1]["type"] == "message" and lines[1]["role"] == "system"

    # Resume from same file id
    t2 = Transcript(system_prompt="sys-ignored", root_dir=tmp_path, session_id=sid)
    msgs = t2.messages
    assert msgs[0] == {"role": "system", "content": "sys"}
    assert msgs[1] == {"role": "user", "content": "hello"}
    assert msgs[2] == {"role": "assistant", "content": "world"}
