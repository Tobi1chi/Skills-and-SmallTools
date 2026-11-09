# SSH Connection Index

This file is a human-readable index for SSH connection aliases.
The service merges `connections.json` with every concrete `Host` in
`~/.ssh/config` (explicit fields here win; missing ones fall back to ssh config).
Prefer adding hosts to `~/.ssh/config` so native `ssh`/`rsync` share them; if you
add one to `connections.json`, keep this Markdown file in sync.

Do not store private key contents, passwords, passphrases, tokens, or other
secrets here. Store only local private key file paths.

## example

| Field | Value |
|-------|-------|
| `host` | `203.0.113.10` |
| `port` | `22` |
| `username` | `ubuntu` |
| `key_path` | `/absolute/path/to/private-key.pem` |
| `verified_at` | `null` |
| `hostname` | `null` |

Connection test:

```sh
uv run --with paramiko python scripts/run_command.py \
  --host 203.0.113.10 \
  --user ubuntu \
  --key /absolute/path/to/private-key.pem \
  --cmd "echo ok"
```
