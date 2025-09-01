# PAI

A small command-line chat app. It talks to a model provider through a simple adapter, keeps a transcript, and can show a banner.

## Requirements
- Python 3.10+
- An API key if you use the OpenAI provider

## Quick start

1) Create and activate a virtual environment

```bash
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

2) Install in editable mode

```bash
pip install -e .
```

3) Provide an API key (OpenAI)

Easiest (environment variable):

```bash
export OPENAI_API_KEY=sk-...          # macOS/Linux
# PowerShell:
# $Env:OPENAI_API_KEY="sk-..."
```

Or via `.env` at the repo root:

```bash
# .env
OPENAI_API_KEY=sk-...
```

Or macOS Keychain (service name `openai`):

```bash
security add-generic-password -a OPENAI_API_KEY -s openai -w sk-...
```

## Configure

Create `config/default.yaml`:

```yaml
model:
  provider: openai          # or: echo
  name: gpt-4o-mini

providers:
  openai:
    params: { temperature: 0.2 }
    timeout: 60
  echo:
    token_delay: 0.08       # seconds per word (streaming)

secrets:
  method: env               # or: [keyring, env]
  mapping:
    openai: { api_key: OPENAI_API_KEY }

storage:
  backend: file
  transcripts_dir: sessions
  resume: null

runtime:
  stream: true

ui:
  config: ui.yaml           # optional; remove to disable banner
```

Optional `config/ui.yaml`:

```yaml
banner:
  enabled: true
  title: PAI
  subtitle: LLM-driven CLI
  show_version: true
  watch_resize: false
  clear_screen: true
  full_width: true
  border_style: cyan
  padding: { top: 0, right: 1, bottom: 0, left: 1 }
  fonts:
    - { max_width: 39,  name: small }
    - { max_width: 79,  name: Standard }
    - { max_width: 9999, name: Slant }
  align: center
```

## Run

```bash
pai
# or
pai --config config/default.yaml
```

In the REPL:

```
/help   /id   /quit
```

## How it works

- `cli.py` starts the REPL and wires everything via `bootstrap.py`.
- `ChatSession` (core) coordinates a turn and keeps message history.
- Providers are pluggable adapters (OpenAI, Echo) discovered via a small registry.
- `ResilientProvider` wraps adapters with retries/backoff and safe streaming behaviour.
- `Transcript` can persist sessions as JSONL under `<repo>/sessions`.

## Folder layout

```
config/           # YAML (default.yaml, ui.yaml)
sessions/         # transcripts (jsonl; gitignored)
src/pai/
  cli.py
  bootstrap.py
  config_loader.py
  core/           # chat_session.py, ports.py
  providers/      # registry.py, openai_adapter.py, echo.py
  resilience/     # resilient_provider.py
  storage/        # transcript.py
  ui/             # banner.py, ui_config.py
  secrets/        # sources.py
  prompts/        # system.txt
tests/            # pytest suite
```

## CI: tests on pull requests

This repository is set up to run the pytest suite automatically on every pull request (and on pushes to the default branch). The workflow lives at `.github/workflows/tests.yml`.

## Troubleshooting

- “No API key for 'openai'”
  - Ensure `OPENAI_API_KEY` is set (env or `.env`), and that `secrets.mapping.openai.api_key` points to it.
- Want to test without network?
  - Use `provider: echo` and run the CLI; it streams a fixed lorem ipsum.
- Banner looks odd or you dislike it?
  - Remove `ui.config` from `default.yaml` to disable.
