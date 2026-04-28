# Codex New Machine Setup

This folder is a cross-machine bootstrap guide for AI agents configuring a new
computer for daily Codex work. It supports:

- macOS
- Windows native
- Windows WSL

Start here. The agent should read this file first, then follow the linked files
in order.

## Distribution Status

This folder is intended to be copied to another user's machine or repository.
It should not depend on the original author's username, home directory, shell
history, local projects, or private credentials.

The only assumption is that the receiving agent can read this folder and run
normal shell or PowerShell commands after asking for permission where required.

Recommended handoff prompt:

```text
Read this folder's README.md and configure this computer for daily Codex work.
Follow the safety rules, detect the platform first, and ask before privileged,
destructive, credential-related, or persistent configuration changes.
```

## Agent Objective

Configure the machine so the user can comfortably use Codex for daily software,
document, data, and automation work.

The agent must:

- Detect the platform before installing anything.
- Prefer existing tools and configuration.
- Ask before privileged, destructive, or persistent system changes.
- Use platform-specific install notes from this folder.
- Verify the final environment and report what changed.

## Hard Rules

- Do not permanently delete files. Use `trash`, Recycle Bin, or an equivalent
  safe-delete tool.
- Python work must use `uv`:
  - `uv venv`
  - `uv pip install`
  - `uv run`
- Do not use plain `pip install` unless the user explicitly approves.
- Ask before:
  - using `sudo` or Administrator privileges
  - deleting files
  - overwriting config files
  - editing shell profile files
  - changing PATH
  - installing large software
  - touching SSH keys, GitHub tokens, or credential stores
- Do not move existing projects.
- Do not overwrite existing Git identity settings.

## Execution Order

1. Read `platform-detection.md`.
2. Classify the machine as one of:
   - macOS
   - Windows native
   - Windows WSL
3. Read the matching platform file:
   - `platforms/macos.md`
   - `platforms/windows-native.md`
   - `platforms/windows-wsl.md`
4. Install or configure only missing items.
5. Read `verification.md` and run the relevant checks.
6. If creating long-lived project rules, use
   `templates/AGENTS.template.md`.
7. Finish with the report format in `final-report.md`.

## Core Tooling Target

The target environment should provide:

- Git and GitHub CLI
- Fast search and shell utilities
- Safe deletion
- Python via `uv`
- Node.js LTS, npm, and pnpm
- PDF, image, document, and media command-line tools
- A predictable workspace directory layout

Core tools:

- `git`
- `gh`
- `curl`
- `wget`
- `rg` / ripgrep
- `fd`
- `jq`
- `tree`
- `trash` or safe-delete equivalent
- `uv`
- Python 3.12+
- Node.js LTS
- `npm`
- `pnpm`
- `ffmpeg`
- Poppler tools, especially `pdftotext`
- ImageMagick, especially `magick`
- `pandoc`

## Workspace Layout

Use this layout unless the user already has a preferred structure.

macOS and WSL:

```text
~/Workspace/
~/Workspace/AI/
~/Workspace/Projects/
~/Workspace/Temp/
```

Windows native:

```text
%USERPROFILE%\Workspace\
%USERPROFILE%\Workspace\AI\
%USERPROFILE%\Workspace\Projects\
%USERPROFILE%\Workspace\Temp\
```

Create missing directories only after checking whether they already exist.

## Notes for Agents

This guide is intentionally conservative. It is better to leave one optional
tool uninstalled and explain why than to make an irreversible system change.

When a package name or install command is uncertain, search official package
manager metadata or ask the user before proceeding.

## Known Limits

- This is a configuration guide, not a fully automated installer.
- Package names can change over time, especially in `winget`.
- Windows PDF tooling varies; WSL may be the more reliable PDF-processing
  environment.
- Company-managed machines may block package managers, PATH edits, or developer
  tools. In that case, report the blocked step and ask the user or IT admin.
