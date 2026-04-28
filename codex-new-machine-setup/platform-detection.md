# Platform Detection

The agent must classify the machine before installing or configuring tools.

## macOS

Run:

```bash
sw_vers
uname -m
command -v brew
brew --version
```

If `sw_vers` works, classify the system as `macOS`.

If Homebrew is missing, ask the user before installing it.

## Windows Native

Use PowerShell.

Run:

```powershell
$PSVersionTable
Get-ComputerInfo | Select-Object OsName, OsVersion, OsArchitecture
winget --version
```

If PowerShell reports Windows and the environment is not WSL, classify the
system as `Windows native`.

If `winget` is missing, tell the user they likely need App Installer from
Microsoft Store or another approved package manager. Do not install Chocolatey
without explicit user approval.

## Windows WSL

In a Unix-like shell, run:

```bash
uname -a
grep -qi microsoft /proc/version && echo "WSL detected"
cat /etc/os-release
```

If `/proc/version` contains `microsoft`, classify the system as `Windows WSL`.

For WSL:

- Prefer work under Linux home, not `/mnt/c`.
- Do not modify Windows native settings unless the user asks.
- Treat Windows browser, GUI, and PATH integration as optional.

## Unknown Platform

If the system cannot be classified as macOS, Windows native, or Windows WSL:

1. Stop before installing packages.
2. Report the detection output.
3. Ask the user how to proceed.
