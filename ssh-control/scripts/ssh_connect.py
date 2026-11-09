"""Connection resolution shared by the service and the short-lived scripts.

OpenSSH compatibility:
- Every concrete `Host` in ~/.ssh/config is an alias, resolved with the same
  HostName/User/Port/IdentityFile/IdentitiesOnly/ProxyCommand/ProxyJump/
  ServerAliveInterval/ConnectTimeout/UserKnownHostsFile/StrictHostKeyChecking/
  HashKnownHosts values native `ssh` uses.
- references/connections.json remains supported; its explicit fields win, and
  missing fields fall back to ssh config. `key_path` is optional.
- Host keys are verified against the same known_hosts file as native ssh. A key
  mismatch is always rejected; an unknown host is recorded on first use
  (OpenSSH `accept-new`) unless StrictHostKeyChecking is `yes`.
- ssh-agent and `<key>-cert.pub` certificates are used as in paramiko/OpenSSH.
"""
import getpass
import json
import os
import re
import shlex
import sys
import threading
from pathlib import Path

import paramiko

SKILL_DIR = Path(__file__).resolve().parents[1]
CONNECTIONS_JSON = SKILL_DIR / "references" / "connections.json"
CONNECTIONS_MD = SKILL_DIR / "references" / "connections.md"
SSH_CONFIG = Path(os.environ.get("SSH_CONTROL_SSH_CONFIG", "~/.ssh/config")).expanduser()
DEFAULT_KNOWN_HOSTS = Path("~/.ssh/known_hosts").expanduser()

_known_hosts_lock = threading.Lock()


class ConnectError(Exception):
    """Connection failure with a stable, secret-free code."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


# ---------------------------------------------------------------- index files

def load_index():
    """Raw entries from connections.json (or the markdown index fallback)."""
    if CONNECTIONS_JSON.exists():
        with CONNECTIONS_JSON.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("connections.json must be an object")
        return data
    return _load_index_markdown()


def _load_index_markdown():
    if not CONNECTIONS_MD.exists():
        return {}
    connections, alias, current = {}, None, {}
    row_re = re.compile(r"^\|\s*`([^`]+)`\s*\|\s*(.*?)\s*\|$")
    for raw in CONNECTIONS_MD.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("## "):
            if alias and current:
                connections[alias] = current
            alias, current = line[3:].strip(), {}
            continue
        match = row_re.match(line)
        if alias and match:
            key, value = match.groups()
            value = value.strip()
            if value.startswith("`") and value.endswith("`"):
                value = value[1:-1]
            current[key] = value
    if alias and current:
        connections[alias] = current
    return connections


def load_ssh_config():
    if SSH_CONFIG.exists():
        return paramiko.SSHConfig.from_path(str(SSH_CONFIG))
    return paramiko.SSHConfig()


def ssh_config_aliases(cfg):
    """Concrete Host names (no wildcards/negations) from ssh config."""
    return sorted(h for h in cfg.get_hostnames()
                  if h and not any(c in h for c in "*?!") and " " not in h)


# ---------------------------------------------------------------- resolution

def _expand_tokens(text, host, port, user):
    return (text.replace("%%", "\0").replace("%h", str(host)).replace("%p", str(port))
            .replace("%r", str(user)).replace("\0", "%"))


def _proxy_jump_command(jump, host, port):
    hops = [h.strip() for h in jump.split(",") if h.strip()]
    if not hops or jump.strip().lower() == "none":
        return None
    argv = ["ssh", "-W", f"{host}:{port}"]
    if len(hops) > 1:
        argv += ["-J", ",".join(hops[:-1])]
    argv.append(hops[-1])
    return " ".join(shlex.quote(a) for a in argv)


def _first(value):
    if isinstance(value, list):
        return value[0] if value else None
    return value


def resolve(alias, index=None, cfg=None):
    """Return a normalized connection config for an alias or ssh-config host."""
    index = load_index() if index is None else index
    cfg = load_ssh_config() if cfg is None else cfg
    item = index.get(alias)
    ssh_aliases = set(ssh_config_aliases(cfg))
    if item is None and alias not in ssh_aliases:
        raise KeyError("unknown connection alias")
    item = dict(item or {})
    lookup_name = alias if alias in ssh_aliases else str(item.get("host") or alias)
    base = cfg.lookup(lookup_name)

    host = item.get("host") or base.get("hostname") or alias
    port = int(item.get("port") or base.get("port") or 22)
    user = item.get("username") or base.get("user") or getpass.getuser()
    identities_only = str(base.get("identitiesonly", "no")).lower() == "yes"
    if item.get("key_path"):
        key_paths = [item["key_path"]]
    else:
        key_paths = list(base.get("identityfile") or [])
    key_paths = [str(Path(p).expanduser()) for p in key_paths]

    proxy = item.get("proxy_command")
    if proxy:
        proxy = _expand_tokens(proxy, host, port, user)
    else:
        proxy = base.get("proxycommand")
        if proxy and proxy.strip().lower() == "none":
            proxy = None
        if not proxy and base.get("proxyjump"):
            proxy = _proxy_jump_command(base["proxyjump"], host, port)

    known_hosts = _first(base.get("userknownhostsfile"))
    known_hosts = str(Path(known_hosts).expanduser()) if known_hosts else str(DEFAULT_KNOWN_HOSTS)
    strict = str(item.get("strict_host_key_checking") or
                 base.get("stricthostkeychecking") or "accept-new").lower()

    return {
        "alias": alias,
        "source": "connections.json" if alias in index else "ssh_config",
        "host": str(host),
        "port": port,
        "username": str(user),
        "key_paths": key_paths,
        "identities_only": identities_only,
        "passphrase": item.get("passphrase"),
        "proxy_command": proxy,
        "known_hosts": known_hosts,
        "strict_host_key_checking": strict,
        "hash_known_hosts": str(base.get("hashknownhosts", "no")).lower() == "yes",
        "keepalive": int(base.get("serveraliveinterval") or 30),
        "connect_timeout": int(base["connecttimeout"]) if base.get("connecttimeout") else None,
        "verified_at": item.get("verified_at"),
        "hostname": item.get("hostname"),
    }


def resolve_all():
    """All aliases: connections.json entries plus concrete ssh-config hosts."""
    index, cfg = load_index(), load_ssh_config()
    result = {}
    for alias in list(index) + ssh_config_aliases(cfg):
        if alias not in result:
            result[alias] = resolve(alias, index, cfg)
    return result


def resolve_target(alias=None, host=None, port=None, user=None, key=None, passphrase=None):
    """For CLI scripts: --alias, or --host treated like `ssh HOST` (ssh config applies)."""
    if alias:
        config = resolve(alias)
    elif host:
        cfg = load_ssh_config()
        index = {host: {}} if host not in ssh_config_aliases(cfg) else {}
        config = resolve(host, index=index, cfg=cfg)
    else:
        raise ValueError("--alias or --host is required")
    if port:
        config["port"] = int(port)
    if user:
        config["username"] = user
    if key:
        config["key_paths"] = [str(Path(key).expanduser())]
    if passphrase:
        config["passphrase"] = passphrase
    return config


def public_connection(config):
    return {
        "alias": config["alias"],
        "source": config["source"],
        "host": config["host"],
        "port": config["port"],
        "username": config["username"],
        "verified_at": config.get("verified_at"),
        "hostname": config.get("hostname"),
        "has_key_path": bool(config["key_paths"]),
        "uses_proxy": bool(config["proxy_command"]),
    }


# ---------------------------------------------------------------- host keys

class AcceptNewPolicy(paramiko.MissingHostKeyPolicy):
    """OpenSSH `accept-new`: record unknown hosts, never accept changed keys."""

    def __init__(self, path, hashed=False):
        self.path = Path(path)
        self.hashed = hashed

    def missing_host_key(self, client, hostname, key):
        entry = paramiko.HostKeys.hash_host(hostname) if self.hashed else hostname
        line = f"{entry} {key.get_name()} {key.get_base64()}\n"
        with _known_hosts_lock:
            self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as f:
                f.write(line)
        client.get_host_keys().add(hostname, key.get_name(), key)
        fingerprint = getattr(key, "fingerprint", key.get_name())
        print(f"ssh-control: recorded new host key for {hostname} ({fingerprint}) in {self.path}",
              file=sys.stderr, flush=True)


def connect(config, timeout=None):
    """Open an authenticated SSHClient. Returns (client, proxy_sock_or_None)."""
    client = paramiko.SSHClient()
    known_hosts = Path(config["known_hosts"])
    if known_hosts.exists():
        client.load_system_host_keys(str(known_hosts))
    strict = config["strict_host_key_checking"]
    if strict in ("yes", "true"):
        client.set_missing_host_key_policy(paramiko.RejectPolicy())
    else:
        client.set_missing_host_key_policy(AcceptNewPolicy(known_hosts, config["hash_known_hosts"]))

    proxy = paramiko.ProxyCommand(config["proxy_command"]) if config["proxy_command"] else None
    key_paths = [p for p in config["key_paths"] if Path(p).exists()]
    try:
        client.connect(
            config["host"],
            port=config["port"],
            username=config["username"],
            key_filename=key_paths or None,
            passphrase=config.get("passphrase"),
            allow_agent=not config["identities_only"],
            look_for_keys=not config["identities_only"] and not key_paths,
            sock=proxy,
            timeout=timeout or config.get("connect_timeout") or 10,
            banner_timeout=30,
            auth_timeout=30,
        )
    except paramiko.BadHostKeyException:
        _close(client, proxy)
        raise ConnectError("host_key_mismatch",
                           f"host key for {config['host']} does not match {known_hosts}; "
                           "verify the server before editing known_hosts")
    except paramiko.SSHException as exc:
        _close(client, proxy)
        text = str(exc)
        if "not found in known_hosts" in text:
            raise ConnectError("host_key_unknown",
                               f"{config['host']} is not in {known_hosts} and StrictHostKeyChecking=yes")
        if isinstance(exc, paramiko.AuthenticationException):
            raise ConnectError("auth_failed", "authentication failed (keyboard-interactive/MFA is not supported)")
        raise ConnectError("ssh_error", "SSH negotiation failed")
    except Exception:
        _close(client, proxy)
        raise ConnectError("connect_failed", f"cannot reach {config['host']}:{config['port']}")
    transport = client.get_transport()
    if transport is None:
        _close(client, proxy)
        raise ConnectError("connect_failed", "SSH transport was not created")
    transport.set_keepalive(config.get("keepalive") or 30)
    return client, proxy


def _close(client, proxy):
    try:
        client.close()
    finally:
        if proxy is not None:
            try:
                proxy.close()
            except Exception:
                pass


def add_target_args(parser):
    """Shared --alias/--host/... options for the short-lived scripts."""
    parser.add_argument("--alias", help="connections.json alias or ~/.ssh/config Host")
    parser.add_argument("--host", help="host name; ~/.ssh/config applies like `ssh HOST`")
    parser.add_argument("--port", type=int)
    parser.add_argument("--user")
    parser.add_argument("--key")
    parser.add_argument("--passphrase", default=None)


def connect_from_args(args, timeout=None):
    """Resolve CLI args and connect; prints a JSON error and exits on failure."""
    try:
        config = resolve_target(args.alias, args.host, args.port, args.user, args.key, args.passphrase)
        return connect(config, timeout=timeout)
    except ConnectError as exc:
        print(json.dumps({"error": exc.code, "detail": exc.message}, ensure_ascii=False))
    except (KeyError, ValueError) as exc:
        print(json.dumps({"error": "invalid_target", "detail": str(exc)}, ensure_ascii=False))
    sys.exit(1)
