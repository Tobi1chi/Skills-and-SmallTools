---
name: ssh-control
description: Operate remote Linux/Unix hosts over SSH from Codex through the ssh-control MCP tools (persistent shell per host, detached long-running jobs, SFTP). Use when the user asks to connect to a server, run remote commands, inspect services or processes, deploy code/configuration, transfer files, or manage a remote machine over SSH.
---

# SSH Control

A local service keeps one SSH connection and one persistent shell per host
alias. **Talk to it through the `ssh-control` MCP tools for every step of
remote work.** MCP tools load lazily: if `ssh_exec` is not visible, search the
available tools for `ssh-control` before considering anything else.

## Which tool

| Need | Tool |
| --- | --- |
| Which hosts exist (after editing ssh config: `reload: true`) | `ssh_hosts` |
| Any command expected to finish within ~30 s | `ssh_exec` |
| Builds, installs, downloads, anything longer or open-ended | `ssh_job` start → wait (pass back `cursor`) |
| Copy files | `ssh_transfer` (absolute local path) |
| Fresh login (group changes, stuck shell) | `ssh_session_reset` |
| SSH password login | `ssh_password_login` request → user enters a password or environment variable in Terminal → status |
| Human confirmation of a high-risk command | `ssh_approval` request → user reviews and responds in Terminal → status, then `ssh_job` |
| Temporary admin access | `ssh_admin_session` request with absolute workspace `log_dir` and optional `log_keep` → user approves and enters sudo password → status; close when finished |

## Multi-step work

- Issue one `ssh_exec` per step and read each result before the next. The shell
  persists, so `cd` and `export` carry over, and each status line ends with the
  current `cwd`; do not chain a whole procedure into one `&&` command or re-`cd`
  every call.
- Use `mode: "exec"` only for isolated commands that need `cwd`/`env`/`stdin`.
- Do not run `ssh host '…'` or `scripts/*.py` through the shell for routine
  work. Native ssh is for `rsync`/`scp` of large trees and for
  `~/.codex-ssh-jobs/codex-job` when the service is down.
- A shell-mode timeout or a job in state `unknown` means the outcome is
  uncertain: inspect the host first, never blindly re-run an install or deploy.

## Fallbacks (only when MCP cannot do it)

- **Password sudo:** A user-approved 15-minute admin session lets MCP `sudo: true`
  run on its bound SSH session without re-entering the password. Without it MCP uses
  `sudo -n`. On
  `sudo_password_required`, run `uv run python scripts/ssh_client.py exec --alias A
  --sudo --sudo-password-env VAR --cmd '…'` from the skill directory. For an approved
  high-risk command the Terminal prompts for sudo password after confirmation.
  Never put a password in a tool argument or command line.
- **Tools missing or connection refused:** follow "Service operations" in
  [usage.md](references/usage.md); `ssh_client.py` is the same service via CLI,
  `scripts/run_command.py` etc. work without it (`uv run --with paramiko python`).

## Rules

- Aliases come from `~/.ssh/config` plus `references/connections.json`. If none
  matches, ask the user for host, port, user and key path; prefer adding the
  host to `~/.ssh/config`.
- On `host_key_mismatch`, stop and tell the user. Never edit `known_hosts` (the
  real host may be off and another device answering on its IP).
- Never print, paste or store private keys, passwords, passphrases, or the
  service token (`.env` in this folder).
- Get explicit user authorization before preparing destructive operations: broad `rm -rf`,
  reboot/shutdown, disk formatting or overwrites, editing sudoers/passwd/shadow,
  stopping critical services, production database writes. For commands caught by the
  service, use `ssh_approval` with a concrete command and explanation. The user must
  personally enter Y in the local Terminal; never approve for them, bypass or rephrase
  the command. Approval is single-use and expires after ten minutes; a closed terminal
  or a lost session never counts as approval. A command may be approved only for the
  host and arguments shown in the Terminal. Poll its returned job; never replay a job
  with unknown outcome.
- When password login is needed, ask the user to enter it or choose an environment
  variable in the Terminal (`ssh_password_login`); never read or print the value in
  chat. If these new tools are not yet available in the current MCP client, use the
  documented `ssh_client.py login` / `approval` commands for this service.
- An admin session is bound to the SSH session, expires 15 minutes after activation,
  and can be closed early with `ssh_admin_session` action `close`. It accepts sudo
  commands only; other commands retain their normal user identity. High-risk commands
  still require their own `ssh_approval`. Admin jobs are attached, not detached;
  disconnect, cancellation or expiry may leave an already-started remote process
  running, so inspect unknown outcomes and do not replay automatically. If the MCP
  client has not loaded the new tool, use the `ssh_client.py admin` fallback.
  Give `log_dir` as an absolute path inside the current workspace (for example its
  `work/ssh-control-logs` directory); `log_keep` is the number of recent task logs,
  default 50 and adjustable by the agent. Each task writes a local JSONL log and
  the returned job status shows its path. Background output stays in the original
  task's log. Active logs are kept until their output streams close; older inactive
  logs are moved to Trash when the limit is exceeded. Do not put secrets in commands
  or output. Remote temporary FIFOs carry output without storing remote log files.
- Report the host, command, relevant output, and exit code or job state; say
  when output was truncated.

Details: [usage.md](references/usage.md) (tool arguments, HTTP API, job
semantics, install), [security-notes.md](references/security-notes.md).
