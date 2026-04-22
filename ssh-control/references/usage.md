# SSH Control Usage

Run all Python commands with `uv`:

```sh
uv run --with paramiko python scripts/<script>.py ...
```

## Persistent HTTP Service

Start the service from the skill directory:

```sh
uv run --with paramiko python scripts/ssh_server.py --bind 127.0.0.1 --port 8765
```

Check service health:

```sh
curl -s http://127.0.0.1:8765/health
```

List connection aliases:

```sh
curl -s http://127.0.0.1:8765/connections
```

Create or reuse a persistent shell session:

```sh
curl -s -X POST http://127.0.0.1:8765/sessions \
  -H 'Content-Type: application/json' \
  -d '{"alias":"example","shell":"/bin/bash"}'
```

Execute in that same shell:

```sh
curl -s -X POST http://127.0.0.1:8765/sessions/<session_id>/exec \
  -H 'Content-Type: application/json' \
  -d '{"cmd":"cd /tmp && pwd","timeout":30}'
```

Close a session:

```sh
curl -s -X DELETE http://127.0.0.1:8765/sessions/<session_id>
```

Stop the service:

```sh
curl -s -X POST http://127.0.0.1:8765/shutdown
```

Notes:

- The service listens on `127.0.0.1` by default.
- It refuses non-local binds unless started with `--allow-nonlocal-bind`.
- Sessions are not closed by idle timeout.
- If SSH is disconnected by the network or remote host, the next exec returns a
  disconnected error and does not auto-reconnect.

## Short-Lived Commands

Run one or more independent commands:

```sh
uv run --with paramiko python scripts/run_command.py \
  --host 203.0.113.10 \
  --user ubuntu \
  --key /absolute/path/to/private-key.pem \
  --cmd "uptime" \
  --cmd "df -h"
```

Run multiple steps in one temporary shell:

```sh
uv run --with paramiko python scripts/interactive_shell.py \
  --host 203.0.113.10 \
  --user ubuntu \
  --key /absolute/path/to/private-key.pem \
  --steps '["cd /var/www/myapp", "pwd", "git status --short"]'
```

Upload a file:

```sh
uv run --with paramiko python scripts/sftp_upload.py \
  --host 203.0.113.10 \
  --user ubuntu \
  --key /absolute/path/to/private-key.pem \
  --local ./nginx.conf \
  --remote /tmp/nginx.conf
```

Download a file:

```sh
uv run --with paramiko python scripts/sftp_download.py \
  --host 203.0.113.10 \
  --user ubuntu \
  --key /absolute/path/to/private-key.pem \
  --remote /var/log/syslog \
  --local ./syslog
```
