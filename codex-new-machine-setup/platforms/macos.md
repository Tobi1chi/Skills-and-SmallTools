# macOS Setup

Use this file only after `platform-detection.md` classifies the system as
macOS.

## Package Manager

Use Homebrew.

Check:

```bash
brew --version
```

If Homebrew is missing, ask before installing it.

## Install Core Tools

First check which tools already exist:

```bash
command -v git
command -v gh
command -v curl
command -v wget
command -v rg
command -v fd
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

Install missing tools with:

```bash
brew install git gh curl wget ripgrep fd jq tree trash uv node pnpm ffmpeg poppler imagemagick pandoc
```

Do not reinstall tools that are already installed unless there is a clear
reason.

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
