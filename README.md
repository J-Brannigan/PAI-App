# PAI

Minimal LLM-driven CLI chat app.

- Name: `pai`
- Python: 3.10 or newer

## What this is

`pai` is a tiny command-line chat loop that talks to a model provider. It ships with:

1. A Typer entry point that starts an interactive REPL.
2. A `ChatSession` object that keeps the running message history in memory.
3. A provider abstraction with an OpenAI implementation and a local Echo stub.
4. A system prompt file you can edit.
5. A simple YAML config loader and macOS Keychain based secret lookup.


## Quick start

1) Create and activate a virtual env

```bash
python -m venv .venv
# macOS or Linux
source .venv/bin/activate
# Windows
.venv\Scripts\activate
```

2) Install in editable mode

```bash
pip install -e .
```

3) Provide an API key

Preferred on macOS: store it in the Keychain under service `openai`.

```bash
security add-generic-password -a OPENAI_API_KEY -s openai -w YOUR_KEY_VALUE
```

Or set an environment variable:

```bash
export OPENAI_API_KEY=YOUR_KEY_VALUE
```

4) Run

```bash
pai
```

Optional config path:

```bash
pai --config path/to/config.yaml
```

5) Use the REPL

It will print:

```
PAI chat. Type /help for commands. Ctrl+C to quit.
```

Type your message and press Enter.

Commands inside the REPL:

```
/help
/exit
/quit
```


## Configuration

Default location: `config/default.yaml` (create it if it does not exist).

Minimal example:

```yaml
model:
  provider: openai
  name: gpt-4o-mini
```

Fields:

- `model.provider`  one of `openai` or `echo`
- `model.name`      the model name sent to the provider

Notes:

- If `provider` is `openai`, an API key is required. The code tries Keychain first (macOS), then the environment variable `OPENAI_API_KEY`.
- If `provider` is `echo`, no key is needed. Echo just returns the text `Okay.` for any input.


## How it works end to end

1) Entry point

`pyproject.toml` declares a console script:

```toml
[project.scripts]
pai = "pai.cli:run"
```

Running `pai` executes `run()`, which invokes the Typer app.

2) CLI

`src/pai/cli.py` defines a Typer callback with an option `--config`, defaulting to `config/default.yaml`. It calls `build_app` to construct the model provider, then creates a `ChatSession` with the system prompt at `src/pai/prompts/system.txt`, prints the banner, and enters a loop:

- read input
- if a REPL command, handle it
- otherwise call `ChatSession.run_turn` and print the reply

3) ChatSession

`src/pai/core/chatSession.py` keeps a list of messages in memory and prepends the system prompt. `run_turn` appends the user message, calls the provider, appends the assistant reply, and returns the reply text. A session id is created from a UTC timestamp. No messages are persisted to disk yet.

4) Providers

OpenAI: `src/pai/providers/openai.py` uses `openai>=1.40` via the `OpenAI` client and calls `chat.completions.create` with `temperature=0.2`.

Echo: `src/pai/providers/echo.py` is an offline stub. It always replies with `Okay.`

5) Secrets

`src/pai/utils/secrets.py` tries to find the OpenAI key in this order:

1. `keyring.get_credential('openai', None)`
2. `keyring.get_password('openai', one of OPENAI_API_KEY, default, openai, or your username)`
3. macOS `security find-generic-password -s openai -w`
4. environment variable `OPENAI_API_KEY`

It returns the first value found, stripped.

6) System prompt

`src/pai/prompts/system.txt` holds the system message. Edit this file to change the assistant behaviour.


## Directory layout

```
project root
  pyproject.toml
  src/
    pai/
      cli.py
      config.py
      utils/
        secrets.py
      providers/
        openai.py
        echo.py
      core/
        chatSession.py
      prompts/
        system.txt
  config/
    default.yaml
```


## Installation notes

`pip install -e .` installs the console script `pai`.


During development you can run the module directly:

```bash
python -m pai.cli
```

But the intended entry point is the console script `pai`.


## Usage examples

Launch with default config:

```bash
pai
```

Launch with a custom model and provider configured in `config/dev.yaml`:

```bash
pai --config config/dev.yaml
```

Inside the REPL:

```
PAI> Hello
…model reply printed here…
PAI> /help
Commands: /help
PAI> /quit
```


## Troubleshooting

I ran `pai chat` and got `unexpected extra argument (chat)`

- There are no subcommands. Just run `pai`. Use `pai --config ...` to select a config file.

OpenAI key not found

- On macOS, confirm a generic password exists for service `openai`:

```bash
security find-generic-password -s openai -w
```

- Or export the environment variable `OPENAI_API_KEY` before running `pai`.

Only `Okay.` comes back

- Check your config. If `provider` is `echo` you will always get `Okay.` Use `openai` for real responses.

Windows or Linux without a system keyring

- Set `OPENAI_API_KEY` in the environment or use a keyring backend supported by the `keyring` package.


## Known issues to fix

1) Error handling and retries

Providers do not catch network errors or rate limits. Basic retries and user friendly error messages would be good.

2) No persistence

Sessions are not saved. Storage layer would keep transcripts or context recovery across runs.

3) No token streaming

The OpenAI provider returns whole responses only. Streaming will give faster perceived latency.

4) No logging or telemetry

## Example config files

`config/default.yaml`

```yaml
model:
  provider: openai
  name: gpt-4o-mini
```

`config/echo.yaml`

```yaml
model:
  provider: echo
  name: local-echo
```