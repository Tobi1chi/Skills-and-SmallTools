---
name: ssh-control
description: Operate remote Linux/Unix hosts over SSH from Codex. Use when the user asks to connect to a server, run remote shell commands, keep a persistent SSH shell, upload or download files with SFTP, inspect services or processes, deploy code/configuration, or manage a remote machine through SSH key authentication.
---

# SSH Control

Use this skill to operate remote hosts through SSH with Python `paramiko`.
It supports both short-lived commands and a local persistent SSH HTTP service
that keeps shell state across calls.

## Runtime Rules

- Use `uv` for all Python execution.
- Do not call `python`, `python3`, or `pip` directly.
- Use `uv run --with paramiko python <script> ...`.
- Do not add `paramiko` to the user's project dependencies unless they ask.

## Connection Index

Before asking for connection details, check:

- `references/connections.json` for machine-readable aliases.
- `references/connections.md` for the human-readable index.

If no matching alias exists, ask for:

| Field | Meaning | Default |
|-------|---------|---------|
| `host` | Server IP or DNS name | Required |
| `port` | SSH port | `22` |
| `username` | SSH username | Required |
| `key_path` | Local private key path | Required |
| `key_passphrase` | Private key passphrase, if any | Optional |

Never paste or store private key contents, passwords, passphrases, or tokens in
the connection index or conversation logs.

## Default Workflow: Unified Client

Use `scripts/ssh_client.py` for HTTP command work; do not write temporary HTTP or
sudo helper scripts. It checks service health, reuses alias sessions, and never
restarts the service or retries a business command after an uncertain result.
Run from the skill directory:

```sh
uv run python scripts/ssh_client.py health
uv run python scripts/ssh_client.py exec --alias example --cmd 'pwd'
uv run python scripts/ssh_client.py exec --alias example --mode exec --cmd 'id'
```

- `shell` (default) preserves cwd/env in the persistent shell. `exec` uses a new
  channel on the same SSH Transport, with explicit cwd/env/stdin when needed.
- `--sudo` always uses an independent channel. For password authentication use
  `--sudo-password-env UBUNTU_KEY`; only the variable name belongs in argv.
  Never print its value. Do not create a permanent root shell or modify sudoers.
- Reload changed aliases with `ssh_client.py reload`. Unknown aliases trigger
  one reload automatically. Existing sessions retain their configuration version;
  alias reuse selects the current version. `--force-new` creates a new Transport
  and shell for changes such as group membership; old sessions remain open.
- For long operations use `jobs start`, then `jobs status` / `jobs wait` with the
  returned cursor. Waiting does not cancel a job. A disconnect gives `unknown`;
  inspect before deciding what to do, never automatically replay installation.
- Jobs are in service memory only; service restart loses task tracking and can
  interrupt execution. Do not restart a shared service on a query failure.

On macOS, prefer the existing `com.openai.codex.ssh-control` LaunchAgent. Check
health before any manual service start. Updating files does not reload a running
process: arrange a safe switch after active jobs/sessions are finished.
For a new service, run:

```sh
uv run --with paramiko python scripts/ssh_server.py --bind 127.0.0.1 --port 8765
```

It listens on localhost without authentication; only trusted local clients should
have access. Sessions do not auto-reconnect. Proxy commands (`%h`, `%p`, `%r`)
and persistent PowerShell remain supported.

Read [usage.md](references/usage.md) for CLI examples, HTTP schemas, cursor and
version semantics, and SFTP; read [security-notes.md](references/security-notes.md)
for sudo input separation, secret handling, and authorization boundaries.

## Short-Lived Fallback Scripts

Use the short-lived scripts when the task is one-off or when the persistent
service is not running:

| Intent | Script |
|--------|--------|
| Run one or more independent commands | `scripts/run_command.py` |
| Run multiple commands in one temporary stateful shell | `scripts/interactive_shell.py` |
| Upload files or directories | `scripts/sftp_upload.py` |
| Download files or directories | `scripts/sftp_download.py` |

`scripts/interactive_shell.py` uses unique sentinels to detect command
completion instead of relying on the remote prompt. Prefer it over
`run_command.py` when command state should persist across steps but the
persistent HTTP service is unnecessary.

## Safety Rules

Require explicit user confirmation before dangerous operations, including:

- Broad deletion such as `rm -rf`.
- Reboot/shutdown/halt/poweroff.
- Formatting or overwriting disks.
- Editing `/etc/sudoers`, `/etc/passwd`, `/etc/shadow`, or similar system files.
- Stopping critical services such as databases or reverse proxies.
- Write operations against production databases.

The persistent HTTP service also rejects several obvious dangerous command
patterns unless started with `--allow-dangerous`.

## Output Expectations

After each operation, summarize:

- Command or endpoint used.
- stdout.
- stderr, if any.
- exit code or HTTP status.

If output is long, show the important part and state that it was truncated.
