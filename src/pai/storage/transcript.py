from __future__ import annotations
import json
import datetime as dt
from pathlib import Path
from typing import Dict, List, Optional, Literal

Role = Literal['system', 'user', 'assistant']
Status = Literal['complete', 'partial']


class Transcript:
    """
    Single transcript class.
    - If root_dir is provided: file-backed JSONL at <root_dir>/<session_id>.jsonl
    - If root_dir is None: in-memory only
    - Exposes .messages for provider calls
    - Handles creating a header and the initial system message
    - If a file already exists for session_id, it resumes from it
    """

    def __init__(
        self,
        system_prompt: str,
        session_id: Optional[str] = None,
        root_dir: Optional[Path] = None,
        header_meta: Optional[Dict] = None,
    ):
        self._system_prompt = system_prompt
        self._root_dir = Path(root_dir) if root_dir else None
        self._session_id = session_id or dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d-%H%M%S')
        self._header_meta = header_meta or {}
        self._messages: List[Dict[str, str]] = []

        # Initialise backing store and in-memory view
        if self._root_dir:
            self._root_dir.mkdir(parents=True, exist_ok=True)
            self._path = self._root_dir / f'{self._session_id}.jsonl'
            if self._path.exists() and self._path.stat().st_size > 0:
                # Resume from existing file
                self._load_from_file()
                # Ensure at least one system message in memory
                if not self._messages or self._messages[0].get('role') != 'system':
                    self._messages.insert(0, {'role': 'system', 'content': system_prompt})
            else:
                # Fresh file with header and system message
                self._messages = [{'role': 'system', 'content': system_prompt}]
                self._write_header_and_system()
        else:
            # Pure in-memory
            self._path = None
            self._messages = [{'role': 'system', 'content': system_prompt}]
            self._records: List[Dict] = []
            self._records.append({
                'type': 'header',
                'ts': dt.datetime.now(dt.timezone.utc).isoformat(),
                'meta': self._header_meta,
            })
            self._records.append({
                'type': 'message',
                'ts': dt.datetime.now(dt.timezone.utc).isoformat(),
                'role': 'system',
                'content': system_prompt,
                'status': 'complete',
            })

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def messages(self) -> List[Dict[str, str]]:
        # Return a shallow copy to avoid accidental mutation
        return list(self._messages)

    def append_message(self, role: Role, content: str, status: Status = 'complete') -> None:
        rec = {
            'type': 'message',
            'ts': dt.datetime.now(dt.timezone.utc).isoformat(),
            'role': role,
            'content': content,
            'status': status,
        }
        if self._root_dir:
            with self._path.open('a', encoding='utf-8') as f:
                f.write(json.dumps(rec, ensure_ascii=False) + '\n')
        else:
            self._records.append(rec)
        if role in ('system', 'user', 'assistant'):
            self._messages.append({'role': role, 'content': content})

    def close(self) -> None:
        # No-op for now. Hook for future rotation or fsync.
        pass

    # Internal helpers

    def _write_header_and_system(self) -> None:
        header = {
            'type': 'header',
            'ts': dt.datetime.now(dt.timezone.utc).isoformat(),
            'meta': self._header_meta,
        }
        sys_msg = {
            'type': 'message',
            'ts': dt.datetime.now(dt.timezone.utc).isoformat(),
            'role': 'system',
            'content': self._system_prompt,
            'status': 'complete',
        }
        with self._path.open('a', encoding='utf-8') as f:
            f.write(json.dumps(header, ensure_ascii=False) + '\n')
            f.write(json.dumps(sys_msg, ensure_ascii=False) + '\n')

    def _load_from_file(self) -> None:
        self._messages = []
        with self._path.open('r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                if obj.get('type') == 'message' and obj.get('role') in ('system', 'user', 'assistant'):
                    self._messages.append({'role': obj['role'], 'content': obj.get('content', '')})
