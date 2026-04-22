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

## Preferred Workflow: Persistent SSH Service

Use the persistent service when multiple commands should reuse one shell and
preserve state such as `cd`, environment variables, shell variables, or long
interactive setup.

Start the local service from the skill directory:

```sh
uv run --with paramiko python scripts/ssh_server.py --bind 127.0.0.1 --port 8765
```

The service:

- Listens on `127.0.0.1` by default.
- Does not use a token by default.
- Keeps sessions open until explicitly closed, the service exits, or SSH is
  disconnected by the network/remote host.
- Does not automatically reconnect disconnected sessions, because shell state
  would be lost.

Core endpoints:

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | Service status and active sessions |
| `GET /connections` | Available aliases without private key paths |
| `POST /sessions` | Create or reuse a persistent shell session |
| `POST /sessions/{session_id}/exec` | Execute a command in that shell |
| `DELETE /sessions/{session_id}` | Close one session |
| `POST /shutdown` | Close all sessions and stop the service |

## Short-Lived Fallback Scripts

Use the short-lived scripts when the task is one-off or when the persistent
service is not running:

| Intent | Script |
|--------|--------|
| Run one or more independent commands | `scripts/run_command.py` |
| Run multiple commands in one temporary shell | `scripts/interactive_shell.py` |
| Upload files or directories | `scripts/sftp_upload.py` |
| Download files or directories | `scripts/sftp_download.py` |

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
