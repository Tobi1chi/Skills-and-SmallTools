# SSH Control Usage

Run Python through `uv`. From the skill directory use the unified client (stdlib
only); the server still requires `uv run --with paramiko python`.

## Client

```sh
uv run python scripts/ssh_client.py health
uv run python scripts/ssh_client.py connections
uv run python scripts/ssh_client.py reload
uv run python scripts/ssh_client.py admin request --alias example --log-dir /absolute/workspace/work/ssh-control-logs --log-keep 50
uv run python scripts/ssh_client.py admin status --alias example
uv run python scripts/ssh_client.py admin close --alias example
uv run python scripts/ssh_client.py login request --alias example --env-var MY_SSH_PASSWORD
uv run python scripts/ssh_client.py login status REQUEST_ID
uv run python scripts/ssh_client.py approval request --alias example --sudo --cmd 'COMMAND' --explanation 'WHAT IT WILL DO'
uv run python scripts/ssh_client.py approval status REQUEST_ID
uv run python scripts/ssh_client.py exec --alias example --cmd 'cd /tmp; pwd'
uv run python scripts/ssh_client.py exec --alias example --mode exec --cwd /tmp --env NAME=value --cmd 'printf "$NAME"; cat' --stdin < input.txt
uv run python scripts/ssh_client.py exec --alias example --force-new --cmd 'id'
uv run python scripts/ssh_client.py exec --session SESSION_ID --cmd 'pwd'
uv run python scripts/ssh_client.py exec --alias example --sudo --sudo-password-env UBUNTU_KEY --cmd 'id'
uv run python scripts/ssh_client.py jobs start --alias example --cmd 'echo "__CODEX_PHASE__:prepare"; sleep 2; echo done'
uv run python scripts/ssh_client.py jobs status JOB_ID
uv run python scripts/ssh_client.py jobs wait JOB_ID --cursor 0 --timeout 30
uv run python scripts/ssh_client.py jobs cancel JOB_ID
uv run python scripts/ssh_client.py jobs list
uv run python scripts/ssh_client.py jobs attach --alias example JOB_ID
uv run python scripts/ssh_client.py jobs start --alias example --attached --cmd 'make'
uv run python scripts/ssh_client.py upload --alias example --local ./app.conf --remote /tmp/app.conf
uv run python scripts/ssh_client.py download --alias example --remote /var/log/app --local ./logs --recursive
```

Native equivalents for detached jobs (no service needed; the alias must be an
`~/.ssh/config` Host):

```sh
ssh example '~/.codex-ssh-jobs/codex-job list'
ssh example '~/.codex-ssh-jobs/codex-job status JOB_ID'
ssh example '~/.codex-ssh-jobs/codex-job tail JOB_ID 100'
ssh example '~/.codex-ssh-jobs/codex-job cancel JOB_ID'
ssh example '~/.codex-ssh-jobs/codex-job run "make -j8"'   # prints "started ID PID"
```

`--url http://127.0.0.1:PORT` precedes the subcommand for an alternate service.
`--stdin` reads business input from local stdin. `--env NAME=VALUE` may repeat;
never use it or `--cmd` to pass passwords. Provision the sudo password in the
client environment through an approved secret source; do not print it. The
LaunchAgent need not inherit that variable. Missing variables fail locally.
The client never starts/restarts a service and never retries a submitted command.

## Terminal confirmation and password login

`ssh_password_login` and `ssh_approval` also have `request` and `status` actions.
Request returns an ID and opens a desktop terminal: Terminal on macOS, a new console
on Windows, or an installed supported terminal emulator on Linux. Linux requires a
graphical desktop and one of x-terminal-emulator, GNOME Terminal, Konsole, XFCE
Terminal, Kitty, Alacritty or xterm. The login prompt accepts a password
with hidden input, or the name of an environment variable. An optional `env_var`
preselects that name, never its value. If the variable is absent from the Terminal
environment, macOS/Linux can source the user's `.zshrc` or `.bashrc` (according to
the user's shell) with output suppressed; Windows also checks user and system
environment variables. Sourcing executes that file's shell code.
The password is supplied to the SSH transport in memory; it is not saved in the
connection configuration or returned to the agent. A successful login is reused
by existing MCP tools until its SSH session closes. For a new or closed session,
repeat the login request. Unknown or changed host keys follow the normal host-key
policy; a mismatch must never be bypassed.

An approval request binds one existing session and one command, its sudo choice,
working directory and explanation. Terminal displays those details; only a human
typing Y executes it. A sudo password can be entered invisibly after confirmation,
or left blank for passwordless sudo. N, Enter, cancellation, expiry (10 minutes),
or a closed SSH session do not execute it. A started request returns a job ID; use
`ssh_job` or `jobs status/wait` to observe it. An approval is single-use. It is an
interactive safeguard for trusted local clients, not a security boundary against
other code running as the same macOS user, which can access the local service and
its temporary approval ticket. A logged-in graphical macOS session is required;
if Terminal cannot open, the request fails without executing.

Approval jobs are attached to the SSH connection. If the service or connection
goes away, their outcome can be unknown; inspect remote state rather than retrying.

`ssh_admin_session` request opens the same terminal and asks the user to confirm
and enter the remote sudo password. It establishes a root shell on the existing SSH
transport; the password is not saved. `sudo: true` then uses that shell for up to
15 minutes from activation. `status` reports expiration and `close` revokes early.
Commands are serialized; sudo jobs are attached even if detached was requested.
After expiration, disconnect, or close no further commands can start on that shell.
For that SSH session, later passwordless sudo requests fail closed until a new
admin session is opened, even if the remote sudo timestamp cache is still valid.
An already-started remote process may outlive channel closure: inspect unknown
results. High-risk commands still need their own terminal approval. The approval
uses the active admin session without asking for the password again; if the session
expires before approval, request a new session and submit a new approval.

Each admin request must specify an absolute local workspace `log_dir`; `log_keep`
sets the number of recent task logs (default 50). One local JSONL file per task
contains its host, command, cwd and stdout/stderr chunks; the job snapshot includes
`log_path`. Output from a background child stays attached to that task's log even
after its foreground shell exits, while its stream remains open. Active logs are
not pruned; when output finishes, older logs beyond the limit are moved to Trash
using `trash` or `trash-put`. If neither command is available, retention cannot
prune and a new task that needs pruning fails before its command is sent. Local
logs may contain sensitive command output. Temporary remote FIFOs carry output;
no remote output log files are created. A disconnect can leave FIFO endpoints in
the remote temporary directory. Each still-running background output stream uses
an SSH channel, so remote SSH session limits apply. A service restart or lost SSH
connection ends capture; a surviving background process can continue remotely.

`exec --mode shell` preserves cwd/env in the persistent shell; use shell commands
to change them. `exec --mode exec` and all sudo/jobs calls use separate POSIX
`/bin/sh` channels on the same authenticated Transport. They do **not** inherit
persistent cwd/env and do not block the shell. Independent execution is POSIX;
Windows users should use persistent PowerShell, e.g.
`--shell 'powershell.exe -NoLogo -NoProfile -Command -'`. No PTY is allocated for sudo.

## HTTP schemas and compatibility

JSON requests/responses; base URL defaults to `http://127.0.0.1:47622`
(override with `--url` or `SSH_CONTROL_URL`). Every request needs
`Authorization: Bearer <token>` (token in the skill's `.env` as
`SSH_CONTROL_TOKEN=...`, created on first use; `SSH_CONTROL_ENV_FILE` relocates it and
the client also honors a `SSH_CONTROL_TOKEN` env var), a local `Host`
(`127.0.0.1`/`localhost`/`[::1]` with the service port) and no `Origin` header;
POST bodies must be `Content-Type: application/json`. Failures: 401
`missing_or_invalid_token`, 403 `host_not_allowed` / `browser_requests_not_allowed`,
415 `content_type_must_be_application_json`. Prefer `ssh_client.py`; for a manual
call read the token into a variable without echoing it:

```sh
TOKEN=$(sed -n 's/^SSH_CONTROL_TOKEN=//p' .env)
curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:47622/health
```

## MCP endpoint

`POST /mcp` speaks MCP streamable HTTP with plain JSON responses (no SSE; `GET`
and `HEAD /mcp` → 405). Same auth as above. Methods: `initialize` (echoes
2024-11-05 / 2025-03-26 / 2025-06-18 / 2026-07-28), `notifications/*` → 202,
`ping`, `tools/list`, `tools/call`. Tool results are text: output, `[stderr]`
block, then one status line such as `[exit 0 · 105 ms · cwd /tmp]` (shell mode
reports the shell's directory after the command; the HTTP/CLI result has `cwd`) or
`[running · 407 ms · cursor 1 · phase build]`.

| Tool | Arguments |
| --- | --- |
| `ssh_hosts` | `reload` |
| `ssh_exec` | `alias`, `cmd`, `mode` (shell/exec), `timeout` (30, max 600), `max_output` (20000, keeps the tail), exec-only `cwd`/`env`/`stdin`, `sudo` (active admin session or `sudo -n`) |
| `ssh_job` | `action` start/wait/status/cancel/list/attach, `alias`, `cmd`, `job_id`, `cursor`, `timeout` (≤50), `attached`, `cwd`/`env`/`stdin`/`sudo`, `max_output` |
| `ssh_transfer` | `alias`, `direction` upload/download, absolute `local`, `remote`, `recursive` |
| `ssh_session_reset` | `alias` (closes its sessions; detached jobs keep running) |
| `ssh_password_login` | `action` request/status, `alias`, optional `env_var`, or `request_id` |
| `ssh_approval` | `action` request/status, `alias`, `cmd`, `explanation`, optional `sudo`/`cwd`, or `approval_id` |
| `ssh_admin_session` | `action` request/status/close, `alias`, request `log_dir` (absolute local workspace path), optional `log_keep` (default 50), or request status with `request_id` |

Codex registration (`~/.codex/config.toml`); the helper prints the auth header
from `.env` on every connection, so the token never sits in config. It runs
through `sh -c`, so `$HOME` expands (adjust the uv path if it lives elsewhere):

```toml
[mcp_servers.ssh-control]
url = "http://127.0.0.1:47622/mcp"
http_headers_helper = "$HOME/.local/bin/uv run --no-project -q python $HOME/.codex/skills/ssh-control/scripts/ssh_token.py headers"
startup_timeout_sec = 20
tool_timeout_sec = 660
```

## Install on a new Mac

Copy this folder to `~/.codex/skills/ssh-control`, then install the LaunchAgent
(the service creates `.env` on first start) and add the `config.toml` entry above:

```sh
SKILL="$HOME/.codex/skills/ssh-control"; UV="$(command -v uv)"
mkdir -p "$SKILL/logs"
cat > ~/Library/LaunchAgents/com.openai.codex.ssh-control.plist <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.openai.codex.ssh-control</string>
  <key>ProgramArguments</key><array>
    <string>$UV</string><string>run</string><string>--with</string><string>paramiko</string>
    <string>python</string><string>$SKILL/scripts/ssh_server.py</string>
    <string>--bind</string><string>127.0.0.1</string><string>--port</string><string>47622</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ProcessType</key><string>Background</string>
  <key>StandardOutPath</key><string>$SKILL/logs/ssh_server.stdout.log</string>
  <key>StandardErrorPath</key><string>$SKILL/logs/ssh_server.stderr.log</string>
  <key>EnvironmentVariables</key><dict>
    <key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
  </dict>
</dict></plist>
EOF
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.openai.codex.ssh-control.plist
```

## Service operations

- Health: `uv run python scripts/ssh_client.py health`. If it fails, check
  `launchctl print gui/$(id -u)/com.openai.codex.ssh-control` and
  `logs/ssh_server.stderr.log` before starting anything by hand.
- Restart after code updates: `launchctl kickstart -k gui/$(id -u)/com.openai.codex.ssh-control`,
  only when no attached job or shell work is in flight (detached jobs survive).
  Never restart because a single query failed; other agents may share the service.
- MCP tools missing in Codex: `codex mcp get ssh-control` should show the entry
  above. Codex sessions started before the entry was added need a restart.
  The skill declares the dependency in `agents/openai.yaml`.
- Token: `<skill>/.env`, created by whichever runs first (service, client, MCP
  header helper). Delete it to rotate; the service re-reads it per request.

Local-only files never belong in git: `.env`, `keys/`, `logs/`, `state/`, and
your real `references/connections.json`/`connections.md` (the repo keeps examples).

Manual handshake for debugging:

```sh
H=$(uv run --no-project -q python scripts/ssh_token.py headers | sed 's/.*"Authorization": "\(.*\)"}/\1/')
curl -s http://127.0.0.1:47622/mcp -H "Authorization: $H" -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

| Endpoint | Request / result |
| --- | --- |
| `GET /health` | Status and sessions including version/current state |
| `GET /connections` | Public aliases; no private key paths |
| `POST /connections/reload` | `{}` → `added`, `modified`, `removed` arrays |
| `POST /sessions` | `alias`, optional `shell`, `connect_timeout` (10), `force_new` (false) → session state and `created` |
| `POST /sessions/{id}/exec` | `cmd`, optional `mode` (`shell` default / `exec`), `timeout` (30), `sudo`, `sudo_password`, `cwd`, `env` object, `stdin` string |
| `POST /sessions/{id}/jobs` | Same execution fields plus `attached` (false). Detached by default (POSIX remotes; not with `sudo_password`); attached jobs stream over one channel → 202 with `job_id`, `detached`, `native` hint |
| `POST /sessions/{id}/sftp` | `direction` (`upload`/`download`), absolute `local`, `remote`, `recursive` → `total`, `failed`, first 50 entries |
| `GET /jobs` | Summaries of tracked jobs (including ones restored after restart) |
| `GET /jobs/{id}` | Status, duration, code, phase and finite output tails; reattaches a detached job |
| `POST /jobs/{id}/wait` | `cursor` (0), `timeout` (30, capped at 50), optional `phase_version` → incremental output and status |
| `POST /jobs/{id}/cancel` | Detached: TERM the remote process group; attached: close the channel |
| `POST /jobs/attach` | `alias`, `job_id` → follow a detached job this service does not know (e.g. started natively) |
| `DELETE /sessions/{id}` | Close session and Transport; attached jobs on it end, detached jobs keep running |
| `POST /shutdown` | Close all sessions/jobs and stop service; coordinate shared users first |

The original `{ "cmd": "pwd", "timeout": 30 }` shell API remains valid.
`cwd`, `env`, `stdin` require independent mode; sudo selects it automatically.
`sudo_password` is an in-memory JSON input intended for the client to supply;
do not put it into curl argv, saved JSON, logs, or chat. A no-password sudo call
uses `sudo -n`; authentication failure returns `error: sudo_password_required`.
With a supplied password it returns `sudo_auth_failed` if authentication fails.
These codes describe pre-command sudo failure; inspect stderr for policy or
missing-sudo issues. No command is replayed. Independent commands use actual SSH
exit codes; nonzero business exit codes still have state `completed`.
Synchronous independent execution includes `job_id`, so an HTTP timeout can be
resolved by querying the job. Persistent shell timeout closes that shell to
prevent later commands from consuming unfinished output; the outcome is uncertain
and the next call reopens the shell (`shell_restarted`, cwd/env reset).

### Configuration versions

Reload parses and validates the complete file before swapping; invalid data
returns 400 and leaves the prior configuration untouched. New/changed/removed
aliases increment per-alias versions. Session `config_version` is immutable;
health adds `config_current` to indicate whether it still matches the registry.
Reuse keys include alias, shell and version; a changed alias creates a fresh
session. A removed alias cannot create sessions but its existing session IDs
continue working. `force_new` bypasses reuse without closing old sessions. A
connect already in flight may finish with its captured version; health reports
it as stale if a reload changed the alias meanwhile. SSH I/O runs outside the
registry lock. Update connections.json atomically to avoid reading a partial file.

### Jobs, phases and bounded output

States: `running` (exit_code null), `completed` (real remote code), `failed`
(pre-command sudo failure), `unknown` (disconnect/channel error/execution timeout;
code null, command may have run). Waiting timeout is not execution timeout.
`duration_ms` freezes on completion. Polling or HTTP disconnect never stops a job.

`status` returns the last 16,384 characters per stream, with `tail_truncated`.
Each job retains at most 1,048,576 Unicode characters across both streams.
`cursor` is an output-event sequence shared across stdout/stderr, not a byte
offset. Use the returned cursor on the next wait; it returns only newer events.
`dropped_before` marks the evicted event boundary; `truncated` means the requested
cursor predates retained output. Lost output cannot be recovered through this
service. Up to 128 jobs are retained; new jobs evict the oldest finished job, or
are rejected when all slots are running. Stream ordering is preserved separately;
no cross-stream time ordering is promised.

Wait returns on completion, explicit phase change, or its bounded timeout, not
on every log line. Pass the previous `phase_version` to catch a phase changed
between requests. Scripts report phases by printing a complete stdout line:

```sh
printf '__CODEX_PHASE__:download\n'
```

The line is kept in stdout and phase metadata; no progress percentages are
inferred.

**Detached jobs** (default for `jobs start`) run as
`~/.codex-ssh-jobs/<id>/run.sh` on the remote host with stdin/stdout/stderr,
pid, started_at and exit_code as plain files (`codex-job`, installed alongside,
is `scripts/remote_job.sh`). The service follows them by byte offset, so an SSH
drop only sets `attached: false` with an explanatory `error` while the state
stays `running`; the next status/wait reattaches without losing output. Job
records persist in `state/jobs/`; after a service restart jobs show
`restored: true`, their cursor restarts at 0, and output is re-read from the
remote files (last 1 MiB). States add `cancelled`; `unknown` with
`remote_process_vanished` means the process died without an exit code (kill -9,
reboot). Finished job directories older than 7 days are pruned on the next start.

**Attached jobs** (`--attached`, sudo with a password, PowerShell sessions, and
synchronous `mode=exec`) end with their channel: a disconnect is `unknown`,
service restart loses them, and 404 means history unavailable, never
permission to replay. Verify remote state through an authorized new session
before any recovery action.

## Short-Lived Commands

All short-lived scripts accept `--alias` (connections.json or `~/.ssh/config`)
or `--host HOST` (ssh config applies, like `ssh HOST`), plus optional
`--port/--user/--key/--passphrase` overrides.

Run one or more independent commands:

```sh
uv run --with paramiko python scripts/run_command.py \
  --alias example \
  --cmd "uptime" \
  --cmd "df -h"
```

Run multiple steps in one temporary shell:

```sh
uv run --with paramiko python scripts/interactive_shell.py \
  --alias example \
  --steps '["cd /var/www/myapp", "pwd", "git status --short"]'
```

`interactive_shell.py` keeps shell state across steps and detects completion
with a unique sentinel instead of the remote prompt. Its JSON result shape is:

```json
{
  "command": "pwd",
  "stdout": "/var/www/myapp\n",
  "stderr": "",
  "exit_code": 0
}
```

Because it uses an interactive PTY, stderr is merged into stdout and the
`stderr` field is kept as an empty compatibility field. The script preserves
ordinary `$`, `#`, `%`, leading/trailing blank lines, trailing spaces, ANSI
control sequences, and CR/LF output where the terminal allows it. It also
disables `errexit` around each wrapped step so that a prior `set -e` does not
prevent the sentinel from being printed.

Each step runs as `eval '<step>' </dev/null`: a step that reads stdin sees EOF
instead of swallowing the sentinel, and an unbalanced quote fails only that step.
Full-screen programs (`vim`, `less`, `top`) and password prompts are still not
supported; use a purpose-built interactive flow.

Upload a file:

```sh
uv run --with paramiko python scripts/sftp_upload.py \
  --alias example \
  --local ./nginx.conf \
  --remote /tmp/nginx.conf
```

Download a file:

```sh
uv run --with paramiko python scripts/sftp_download.py \
  --alias example \
  --remote /var/log/syslog \
  --local ./syslog
```
