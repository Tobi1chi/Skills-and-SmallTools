---
name: ssh-control
description: Operate remote Linux/Unix hosts over SSH from Codex. Use when the user asks to connect to a server, run remote shell commands, keep a persistent SSH shell, run long remote jobs, upload or download files with SFTP, inspect services or processes, deploy code/configuration, or manage a remote machine through SSH key authentication.
---

# SSH Control

A local service (LaunchAgent `com.openai.codex.ssh-control`, `127.0.0.1:47622`)
keeps one authenticated SSH connection and persistent shell per alias. Use it
through the **`ssh-control` MCP tools** first; the CLI client and short-lived
scripts below are fallbacks.

## 1. MCP tools (default)

| Tool | Use for |
| --- | --- |
| `ssh_hosts` | List aliases and open sessions (`reload: true` after editing ssh config) |
| `ssh_exec` | Short commands. `mode=shell` (default) keeps cwd/env across calls; `mode=exec` is an isolated `/bin/sh` with `cwd`/`env`/`stdin` |
| `ssh_job` | Anything that may run > ~30 s: `start` → `wait` (pass the returned `cursor`) → … ; `status`, `cancel`, `list`, `attach` |
| `ssh_transfer` | SFTP `upload`/`download`; `local` must be absolute |
| `ssh_session_reset` | Fresh connection/shell for an alias (e.g. after group changes) |

- Results are text: output, a `[stderr]` block, then one status line
  (`[exit 1 · 108 ms]`, `[running · cursor 3 · phase build]`). Output keeps the
  newest `max_output` chars (20000); raise it only when needed.
- Shell mode runs each command as `eval '<cmd>' </dev/null`: no stdin (prompts
  get EOF), an unbalanced quote fails only that command. A shell-mode timeout
  closes the shell (`outcome uncertain`); the next call reports
  `shell_restarted` and cwd/env are reset.
- `ssh_job start` runs **detached** under `~/.codex-ssh-jobs/<id>/` on the host
  and survives SSH drops, service restarts and Mac sleep. `unknown` means the
  outcome is uncertain: inspect before acting, never replay an install. Print
  `__CODEX_PHASE__:<name>` lines to make `wait` return on phase changes.
- `sudo: true` uses `sudo -n` only. If it returns `sudo_password_required`, use
  the CLI with `--sudo-password-env VAR` (section 2); never put a password in a
  tool argument.

If the tools are missing or fail with a connection error, check the service
with the CLI `health` command below. The MCP server is declared in
`agents/openai.yaml` and registered in `~/.codex/config.toml` as
`[mcp_servers.ssh-control]`; its `http_headers_helper` runs
`scripts/ssh_token.py headers` to send the token.

## 2. CLI fallback (same service, same sessions and jobs)

Use when MCP is unavailable, for password sudo, or for scripting. Run from the
skill directory with `uv` (never call `python`/`pip` directly):

```sh
uv run python scripts/ssh_client.py health
uv run python scripts/ssh_client.py exec --alias A --cmd 'pwd'
uv run python scripts/ssh_client.py exec --alias A --sudo --sudo-password-env UBUNTU_KEY --cmd 'id'
uv run python scripts/ssh_client.py jobs start --alias A --cmd 'make -j8'
uv run python scripts/ssh_client.py jobs wait JOB_ID --cursor 0 --timeout 30
uv run python scripts/ssh_client.py upload --alias A --local /abs/file --remote /tmp/file
```

The client never restarts the service or retries a submitted command. For the
full HTTP API, cursors, config versions and job semantics read
[usage.md](references/usage.md).

Detached jobs also work with plain ssh, without the service:
`ssh A '~/.codex-ssh-jobs/codex-job list|status ID|tail ID [N]|cancel ID|run "CMD"'`;
`ssh_job attach` / `jobs attach` follows a job started that way.

If the service is down, check `launchctl print gui/$(id -u)/com.openai.codex.ssh-control`
before starting anything by hand. Updated code needs a restart
(`launchctl kickstart -k gui/$(id -u)/com.openai.codex.ssh-control`); do it only
when no attached job or shell work is in flight (detached jobs are safe).

## 3. Short-lived scripts (no service)

`scripts/run_command.py`, `interactive_shell.py`, `sftp_upload.py`,
`sftp_download.py`, run with `uv run --with paramiko python <script>`. All take
`--alias A` or `--host HOST` (resolved through `~/.ssh/config` like `ssh HOST`)
and verify host keys like the service. For directory sync, native `rsync -a`
with the ssh-config alias is usually better.

## Connections and host keys

Aliases = every concrete `Host` in `~/.ssh/config` (HostName, User, Port,
IdentityFile, IdentitiesOnly, ProxyCommand, ProxyJump, UserKnownHostsFile,
StrictHostKeyChecking, ServerAliveInterval honored) merged with
`references/connections.json` (explicit fields win). Prefer adding new hosts to
`~/.ssh/config` so native `ssh`/`rsync` share them. If no alias matches, ask the
user for host, port, username and key path.

Host keys are checked against the same `known_hosts` as native ssh: unknown
hosts are recorded on first use (`accept-new`), a changed key fails with
`host_key_mismatch`. **Never edit `known_hosts` to get past a mismatch**; report
it to the user (a different device may be answering on that IP while the real
host is off).

## Token

The service token lives in `<skill>/.env` (`SSH_CONTROL_TOKEN=...`, mode 600).
Whichever runs first (service, CLI client or MCP header helper) creates it;
everything else reads the same file. To rotate, delete `.env`; the service
re-reads it per request. Never print, paste or log the token, and never copy it
into `config.toml` or the conversation.

Never paste or store private key contents, passwords, passphrases, or tokens in
the connection index or conversation logs.

## Safety rules

Require explicit user confirmation before dangerous operations, including:

- Broad deletion such as `rm -rf`.
- Reboot/shutdown/halt/poweroff.
- Formatting or overwriting disks.
- Editing `/etc/sudoers`, `/etc/passwd`, `/etc/shadow`, or similar system files.
- Stopping critical services such as databases or reverse proxies.
- Write operations against production databases.

The service (MCP and CLI alike) also rejects obvious destructive forms unless
started with `--allow-dangerous`; read-only commands such as `cat /etc/passwd` or
`fdisk -l` pass. A rejection is a seatbelt, not authorization: do not rephrase a
command to slip past it, and the confirmation rule above still applies. See
[security-notes.md](references/security-notes.md).

## Output expectations

After each operation, summarize the host and command, the relevant stdout,
stderr if any, and the exit code or state. If output is long or was truncated,
show the important part and say so.
