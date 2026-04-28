# Windows WSL Setup

Use this file only after `platform-detection.md` classifies the system as
Windows WSL.

## Scope

Configure the Linux WSL environment for Codex work. Do not modify Windows native
settings unless the user explicitly asks.

Prefer storing active projects under:

```text
~/Workspace/
```

Avoid using `/mnt/c` for active development unless the user has a reason,
because file watching and filesystem performance can be worse there.

## Detect Distribution

Run:

```bash
cat /etc/os-release
```

If Ubuntu or Debian, use the commands below. For other WSL distributions, adapt
the package manager and ask before continuing if uncertain.

## Ubuntu or Debian WSL

Check existing tools:

```bash
command -v git
command -v gh
command -v curl
command -v wget
command -v rg
command -v fdfind || command -v fd
command -v jq
command -v tree
command -v trash
command -v uv
command -v python3
command -v node
command -v npm
command -v pnpm
command -v ffmpeg
command -v pdftotext
command -v magick
command -v pandoc
```

Ask before running `sudo`.

Install available packages:

```bash
sudo apt update
sudo apt install git curl wget ripgrep fd-find jq tree trash-cli python3 python3-venv nodejs npm ffmpeg poppler-utils imagemagick pandoc
```

Notes:

- Debian and Ubuntu often install `fd` as `fdfind`.
- `gh` may require GitHub's official apt repository.
- `uv` should be installed from an official source or package manager after
  asking the user.
- `pnpm` can be installed through Corepack or npm after Node.js is available.

## Git Defaults

Inspect existing settings:

```bash
git config --global user.name
git config --global user.email
git config --global pull.rebase
git config --global init.defaultBranch
```

If `user.name` or `user.email` is missing, ask the user for values.

Recommended non-identity defaults:

```bash
git config --global init.defaultBranch main
git config --global pull.rebase true
```

Do not overwrite existing identity values.

## GitHub CLI

Check:

```bash
gh auth status
```

If not logged in, ask the user to run:

```bash
gh auth login
```

Do not handle tokens or SSH keys unless the user explicitly asks.

## Workspace Directories

Create missing directories:

```text
~/Workspace/
~/Workspace/AI/
~/Workspace/Projects/
~/Workspace/Temp/
```

Do not move existing directories or projects.
