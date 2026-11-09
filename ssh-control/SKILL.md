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

## Multi-step work

- Issue one `ssh_exec` per step and read each result before the next. The shell
  persists, so `cd` and `export` carry over; do not chain a whole procedure
  into one `&&` command or re-`cd` every call.
- Use `mode: "exec"` only for isolated commands that need `cwd`/`env`/`stdin`.
- Do not run `ssh host '…'` or `scripts/*.py` through the shell for routine
  work. Native ssh is for `rsync`/`scp` of large trees and for
  `~/.codex-ssh-jobs/codex-job` when the service is down.
- A shell-mode timeout or a job in state `unknown` means the outcome is
  uncertain: inspect the host first, never blindly re-run an install or deploy.

## Fallbacks (only when MCP cannot do it)

- **Password sudo:** MCP `sudo` is passwordless (`sudo -n`). On
  `sudo_password_required`, run `uv run python scripts/ssh_client.py exec --alias A
  --sudo --sudo-password-env VAR --cmd '…'` from the skill directory. Never put a
  password in a tool argument or command line.
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
- Get explicit user confirmation before destructive operations: broad `rm -rf`,
  reboot/shutdown, disk formatting or overwrites, editing sudoers/passwd/shadow,
  stopping critical services, production database writes. The service also
  rejects obvious destructive commands; never rephrase one to slip past it.
- Report the host, command, relevant output, and exit code or job state; say
  when output was truncated.

Details: [usage.md](references/usage.md) (tool arguments, HTTP API, job
semantics, install), [security-notes.md](references/security-notes.md).
