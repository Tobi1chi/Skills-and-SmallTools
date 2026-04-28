# Windows Native Setup

Use this file only after `platform-detection.md` classifies the system as
Windows native.

## Package Manager

Use PowerShell and prefer `winget`.

Check:

```powershell
winget --version
```

If `winget` is missing, tell the user they may need App Installer from Microsoft
Store. Do not install Chocolatey unless the user explicitly approves.

## Install Core Tools

Check whether each command already exists before installing it:

```powershell
git --version
gh --version
curl --version
wget --version
rg --version
fd --version
jq --version
uv --version
python --version
node --version
npm --version
pnpm --version
ffmpeg -version
magick -version
pandoc --version
```

Recommended winget packages:

```powershell
winget install Git.Git
winget install GitHub.cli
winget install cURL.cURL
winget install GNU.Wget2
winget install BurntSushi.ripgrep.MSVC
winget install sharkdp.fd
winget install jqlang.jq
winget install astral-sh.uv
winget install Python.Python.3.12
winget install OpenJS.NodeJS.LTS
winget install pnpm.pnpm
winget install Gyan.FFmpeg
winget install ImageMagick.ImageMagick
winget install JohnMacFarlane.Pandoc
```

`tree` is commonly available in Windows as `tree.com`, so verify before trying
to install another implementation.

## Poppler on Windows

Poppler availability through `winget` can vary. First search:

```powershell
winget search poppler
```

If no reliable package is available, present options:

- Install Poppler through a trusted Windows build.
- Use WSL for PDF extraction and rendering.
- Use a Python package for specific PDF workflows when sufficient.

Ask before installing unofficial builds.

## Safe Deletion

Do not use permanent deletion commands for user files.

Preferred options:

- Recycle Bin from Explorer.
- A PowerShell safe-delete command or module, only after user approval.
- A project-provided `trash` tool if already installed.

## Git Defaults

Inspect existing settings:

```powershell
git config --global user.name
git config --global user.email
git config --global pull.rebase
git config --global init.defaultBranch
```

If `user.name` or `user.email` is missing, ask the user for values.

Recommended non-identity defaults:

```powershell
git config --global init.defaultBranch main
git config --global pull.rebase true
```

Do not overwrite existing identity values.

## GitHub CLI

Check:

```powershell
gh auth status
```

If not logged in, ask the user to run:

```powershell
gh auth login
```

Do not handle tokens or SSH keys unless the user explicitly asks.

## Workspace Directories

Create missing directories:

```text
%USERPROFILE%\Workspace\
%USERPROFILE%\Workspace\AI\
%USERPROFILE%\Workspace\Projects\
%USERPROFILE%\Workspace\Temp\
```

Do not move existing directories or projects.
