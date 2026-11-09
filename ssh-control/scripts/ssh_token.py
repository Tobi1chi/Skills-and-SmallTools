"""Local service token kept in the skill folder's .env file (stdlib only).

The first caller (service, CLI client or Codex's MCP header helper) creates
`<skill>/.env` with mode 0600; everyone afterwards reads the same file. Delete
the file to rotate: the next caller writes a new token and the running service
picks it up on the next request (it re-reads the file every time).

  uv run --no-project -q python scripts/ssh_token.py headers   # Codex http_headers_helper
  uv run --no-project -q python scripts/ssh_token.py init      # create if missing, print path
"""
import json
import os
import secrets
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = Path(os.environ.get("SSH_CONTROL_ENV_FILE", SKILL_DIR / ".env")).expanduser()
LEGACY_TOKEN_FILE = SKILL_DIR / "state" / "token"
KEY = "SSH_CONTROL_TOKEN"
HEADER = "# ssh-control local service token. Created on first use; delete this file to rotate.\n"


def _read(path):
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith(KEY + "="):
            value = line.split("=", 1)[1].strip().strip('"').strip("'")
            return value if len(value) >= 32 else None
    return None


def ensure_token(path=ENV_FILE):
    """Return the token, creating the .env file (0600) on first use."""
    token = _read(path)
    if token:
        if path.stat().st_mode & 0o077:
            os.chmod(path, 0o600)
        return token
    legacy = None
    try:
        legacy = LEGACY_TOKEN_FILE.read_text(encoding="utf-8").strip() or None
    except OSError:
        pass
    token = legacy if legacy and len(legacy) >= 32 else secrets.token_urlsafe(32)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".tmp{os.getpid()}")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(HEADER + f"{KEY}={token}\n")
    try:
        os.link(tmp, path)          # atomic create-if-absent: concurrent first users agree
    except FileExistsError:
        pass
    finally:
        tmp.unlink(missing_ok=True)
    winner = _read(path)
    if winner and legacy:
        LEGACY_TOKEN_FILE.unlink(missing_ok=True)
    return winner or token


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else "init"
    token = ensure_token()
    if action == "headers":
        print(json.dumps({"Authorization": "Bearer " + token}))
    elif action == "init":
        print(str(ENV_FILE))
    else:
        print("usage: ssh_token.py [init|headers]", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
