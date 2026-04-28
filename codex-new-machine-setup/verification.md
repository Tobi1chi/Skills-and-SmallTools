# Verification Checklist

Run the checks matching the detected platform. Summarize versions and failures
in the final report.

## macOS and WSL

```bash
git --version
gh --version
curl --version
wget --version
rg --version
fd --version || fdfind --version
jq --version
tree --version
trash --version
uv --version
python3 --version
node --version
npm --version
pnpm --version
ffmpeg -version
pdftotext -v
magick -version
pandoc --version
```

## Windows Native PowerShell

```powershell
git --version
gh --version
curl --version
wget --version
rg --version
fd --version
jq --version
tree /?
uv --version
python --version
node --version
npm --version
pnpm --version
ffmpeg -version
magick -version
pandoc --version
```

## Git Checks

```bash
git config --global user.name
git config --global user.email
git config --global pull.rebase
git config --global init.defaultBranch
```

PowerShell uses the same `git config` commands.

## GitHub CLI Check

```bash
gh auth status
```

PowerShell uses the same command.

## Python uv Smoke Test

Run inside a temporary test directory. Use safe deletion after the test.

```bash
uv venv
uv run python --version
```

PowerShell:

```powershell
uv venv
uv run python --version
```

## Node Smoke Test

```bash
node --version
npm --version
pnpm --version
```

PowerShell uses the same commands.

## Result Rules

For every failed check, report:

- command
- error summary
- likely cause
- recommended next step
- whether user approval is needed
