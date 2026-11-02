# Run with: uv run --with paramiko python scripts/ssh_server.py --bind 127.0.0.1 --port 8765
r"""
Persistent SSH HTTP service for ssh-control.

This service keeps shell sessions open until they are explicitly deleted, the
service shuts down, or the SSH transport is closed by the network/remote host.
It intentionally listens on localhost by default and does not expose private key
contents through any endpoint.
"""

import argparse
import json
import re
import signal
import sys
import threading
import time
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import paramiko
from ssh_execution import Job, run_channel, command_line


SKILL_DIR = Path(__file__).resolve().parents[1]
CONNECTIONS_JSON = SKILL_DIR / "references" / "connections.json"
CONNECTIONS_MD = SKILL_DIR / "references" / "connections.md"

DANGEROUS_PATTERNS = [
    re.compile(r"(^|[;&|]\s*)rm\s+(-[^\s]*r[^\s]*f|-+[^\s]*f[^\s]*r)\s+/(?:\s|$)"),
    re.compile(r"(^|[;&|]\s*)mkfs(?:\.[\w-]+)?\b"),
    re.compile(r"(^|[;&|]\s*)(shutdown|reboot|halt|poweroff)\b"),
    re.compile(r"(^|[;&|]\s*)dd\s+.*\bof=/dev/"),
    re.compile(r"(^|[;&|]\s*)iptables\s+-F\b"),
    re.compile(r"(^|[;&|]\s*)chmod\s+-R\s+777\b"),
    re.compile(r"\b(DROP|TRUNCATE)\s+TABLE\b", re.IGNORECASE),
    re.compile(r"/etc/(sudoers|passwd|shadow|group)\b"),
]


def load_private_key(key_path, passphrase=None):
    for key_class in [paramiko.RSAKey, paramiko.Ed25519Key, paramiko.ECDSAKey]:
        try:
            return key_class.from_private_key_file(str(key_path), password=passphrase)
        except Exception:
            continue
    raise ValueError(f"无法识别私钥格式或密码错误：{key_path}")


def load_connections():
    if CONNECTIONS_JSON.exists():
        with CONNECTIONS_JSON.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return {
            alias: {
                "host": item["host"],
                "port": int(item.get("port", 22)),
                "username": item["username"],
                "key_path": item["key_path"],
                "proxy_command": item.get("proxy_command"),
                "verified_at": item.get("verified_at"),
                "hostname": item.get("hostname"),
            }
            for alias, item in data.items()
        }
    return load_connections_from_markdown()


def load_connections_from_markdown():
    if not CONNECTIONS_MD.exists():
        return {}

    connections = {}
    current_alias = None
    current = {}
    row_re = re.compile(r"^\|\s*`([^`]+)`\s*\|\s*(.*?)\s*\|$")

    for raw_line in CONNECTIONS_MD.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("## "):
            if current_alias and current:
                connections[current_alias] = current
            current_alias = line[3:].strip()
            current = {}
            continue
        match = row_re.match(line)
        if current_alias and match:
            key, value = match.groups()
            value = value.strip()
            if value.startswith("`") and value.endswith("`"):
                value = value[1:-1]
            current[key] = int(value) if key == "port" else value

    if current_alias and current:
        connections[current_alias] = current
    return connections


def public_connection(alias, item):
    return {
        "alias": alias,
        "host": item.get("host"),
        "port": item.get("port", 22),
        "username": item.get("username"),
        "verified_at": item.get("verified_at"),
        "hostname": item.get("hostname"),
        "has_key_path": bool(item.get("key_path")),
        "uses_proxy": bool(item.get("proxy_command")),
    }


def is_dangerous_command(command):
    return any(pattern.search(command) for pattern in DANGEROUS_PATTERNS)


class PersistentShellSession:
    def __init__(self, session_id, alias, config, shell="/bin/bash", connect_timeout=10):
        self.session_id = session_id
        self.alias = alias
        self.config = config
        self.shell = shell
        self.is_powershell = shell.lower().split()[0] in (
            "powershell",
            "powershell.exe",
            "pwsh",
            "pwsh.exe",
        )
        self.created_at = time.time()
        self.last_used_at = None
        self.lock = threading.Lock()

        key_path = Path(config["key_path"]).expanduser()
        pkey = load_private_key(key_path, config.get("passphrase"))

        self.proxy = None
        proxy_command = config.get("proxy_command")
        if proxy_command:
            proxy_command = (
                proxy_command.replace("%h", str(config["host"]))
                .replace("%p", str(config.get("port", 22)))
                .replace("%r", str(config["username"]))
            )
            self.proxy = paramiko.ProxyCommand(proxy_command)

        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.client.connect(
            config["host"],
            port=int(config.get("port", 22)),
            username=config["username"],
            pkey=pkey,
            sock=self.proxy,
            timeout=connect_timeout,
        )
        transport = self.client.get_transport()
        if transport is None:
            raise RuntimeError("SSH transport was not created")
        transport.set_keepalive(30)

        self.channel = transport.open_session()
        self.channel.settimeout(0.2)
        self.channel.exec_command(shell)
        self._drain_startup()

    def _drain_startup(self):
        deadline = time.time() + 0.5
        while time.time() < deadline:
            self._recv_available()
            time.sleep(0.05)

    def _recv_available(self):
        stdout = []
        stderr = []
        while self.channel.recv_ready():
            stdout.append(self.channel.recv(65535).decode("utf-8", errors="replace"))
        while self.channel.recv_stderr_ready():
            stderr.append(self.channel.recv_stderr(65535).decode("utf-8", errors="replace"))
        return "".join(stdout), "".join(stderr)

    def is_connected(self):
        transport = self.client.get_transport()
        return bool(
            transport
            and transport.is_active()
            and not self.channel.closed
            and not self.channel.exit_status_ready()
        )

    def execute(self, command, timeout=30, allow_dangerous=False):
        if not allow_dangerous and is_dangerous_command(command):
            return {
                "command": command,
                "stdout": "",
                "stderr": "危险命令已被 ssh_server.py 拒绝执行",
                "exit_code": -2,
                "duration_ms": 0,
            }

        with self.lock:
            if not self.is_connected():
                return {
                    "command": command,
                    "stdout": "",
                    "stderr": "SSH session is disconnected; v1 does not auto-reconnect",
                    "exit_code": -1,
                    "duration_ms": 0,
                }

            marker = f"__CODEX_SSH_DONE_{uuid.uuid4().hex}__"
            if self.is_powershell:
                payload = (
                    "$global:LASTEXITCODE = 0\n"
                    f"{command}\n"
                    "$__codex_success = $?\n"
                    "$__codex_status = if ($__codex_success) { "
                    "[int]$global:LASTEXITCODE } elseif ($global:LASTEXITCODE -ne 0) { "
                    "[int]$global:LASTEXITCODE } else { 1 }\n"
                    f"[Console]::Error.WriteLine(\"{marker}ERR\")\n"
                    f"[Console]::Out.WriteLine(\"`n{marker}:{{0}}\" -f $__codex_status)\n"
                )
            else:
                payload = (
                    f"{command}\n"
                    "__codex_status=$?\n"
                    f"printf '{marker}ERR\\n' >&2\n"
                    f"printf '\\n{marker}:%s\\n' \"$__codex_status\"\n"
                )
            started = time.time()
            stdout_chunks = []
            stderr_chunks = []

            try:
                self.channel.sendall(payload)
            except Exception as exc:
                return {
                    "command": command,
                    "stdout": "",
                    "stderr": f"SSH write failed: {exc}",
                    "exit_code": -1,
                    "duration_ms": int((time.time() - started) * 1000),
                }

            marker_re = re.compile(re.escape(marker) + r":(-?\d+)\r?\n")
            deadline = started + timeout
            exit_code = None
            stderr_done = False
            while time.time() < deadline:
                out, err = self._recv_available()
                if err:
                    stderr_chunks.append(err)
                if out:
                    stdout_chunks.append(out)
                    stdout_text = "".join(stdout_chunks)
                    match = marker_re.search(stdout_text)
                    if match:
                        exit_code = int(match.group(1))
                        before = stdout_text[: match.start()]
                        after = stdout_text[match.end() :]
                        stdout_chunks = [before + self._strip_marker_tail(after)]
                stderr_text = "".join(stderr_chunks)
                if re.search(re.escape(marker) + r"ERR\r?\n", stderr_text):
                    stderr_done = True
                    stderr_chunks = [re.sub(re.escape(marker) + r"ERR\r?\n", "", stderr_text)]
                if exit_code is not None and stderr_done:
                    break
                if not self.is_connected():
                    break
                time.sleep(0.05)

            out, err = self._recv_available()
            if out:
                stdout_chunks.append(out)
            if err:
                stderr_chunks.append(err)

            duration_ms = int((time.time() - started) * 1000)
            self.last_used_at = time.time()

            if exit_code is None or not stderr_done:
                try:
                    self.channel.close()
                except Exception:
                    pass
                return {
                    "command": command,
                    "stdout": "".join(stdout_chunks),
                    "stderr": "".join(stderr_chunks) + f"\nCommand timed out after {timeout}s",
                    "exit_code": -1,
                    "duration_ms": duration_ms,
                }

            return {
                "command": command,
                "stdout": "".join(stdout_chunks),
                "stderr": "".join(stderr_chunks),
                "exit_code": exit_code,
                "duration_ms": duration_ms,
            }

    @staticmethod
    def _strip_marker_tail(text):
        lines = text.splitlines(keepends=True)
        if lines and lines[0].strip() == "":
            return "".join(lines[1:])
        return text

    def close(self):
        try:
            if not self.channel.closed:
                self.channel.close()
        finally:
            self.client.close()
            if self.proxy is not None:
                self.proxy.close()

    def public_state(self):
        return {
            "session_id": self.session_id,
            "alias": self.alias,
            "host": self.config.get("host"),
            "username": self.config.get("username"),
            "shell": self.shell,
            "connected": self.is_connected(),
            "created_at": self.created_at,
            "last_used_at": self.last_used_at,
            "config_version": getattr(self, "config_version", 1),
        }


class SessionRegistry:
    def __init__(self, connections, allow_dangerous=False):
        self.connections = connections
        self.allow_dangerous = allow_dangerous
        self.lock = threading.Lock()
        self.sessions = {}
        self.alias_index = {}
        self.versions = {alias: 1 for alias in connections}
        self.reload_lock = threading.Lock()
        self.jobs = {}

    def list_sessions(self):
        with self.lock:
            states = []
            for session in self.sessions.values():
                state = session.public_state()
                state["config_current"] = (session.alias in self.connections and
                                           session.config_version == self.versions.get(session.alias))
                states.append(state)
            return states

    def reload(self):
        # Parse first; exceptions leave both configuration and versions intact.
        with self.reload_lock:
            connections = load_connections()
            for item in connections.values():
                for field in ("host", "username", "key_path"):
                    if not isinstance(item.get(field), str) or not item[field]:
                        raise ValueError("missing connection field: " + field)
                if not 1 <= int(item.get("port", 22)) <= 65535:
                    raise ValueError("invalid SSH port")
            with self.lock:
                old = self.connections
                added = sorted(connections.keys() - old.keys())
                removed = sorted(old.keys() - connections.keys())
                modified = sorted(k for k in old.keys() & connections.keys() if old[k] != connections[k])
                for alias in added + removed + modified:
                    self.versions[alias] = self.versions.get(alias, 0) + 1
                self.connections = connections
            return dict(added=added, modified=modified, removed=removed)

    def get_or_create(self, alias, shell="/bin/bash", connect_timeout=10, force_new=False):
        with self.lock:
            missing = alias not in self.connections
        if missing:
            self.reload()
        with self.lock:
            if alias not in self.connections:
                raise KeyError("unknown connection alias")
            config = dict(self.connections[alias])
            version = self.versions[alias]
            key = (alias, shell, version)
            existing = self.sessions.get(self.alias_index.get(key))
            if not force_new and existing and existing.is_connected():
                return existing, False
        # SSH connect/open/startup must never hold the registry lock.
        session = PersistentShellSession(uuid.uuid4().hex, alias, config, shell, connect_timeout)
        session.config_version = version
        with self.lock:
            winner = self.sessions.get(self.alias_index.get(key))
            if not force_new and winner and winner.is_connected():
                reuse = winner
            else:
                self.sessions[session.session_id] = session
                self.alias_index[key] = session.session_id
                reuse = None
        if reuse:
            session.close()
            return reuse, False
        return session, True

    def start_job(self, session, body):
        if not self.allow_dangerous and is_dangerous_command(body["cmd"]):
            raise PermissionError("dangerous command rejected")
        command_line(body, "validation")
        job = Job()
        with self.lock:
            # Bound retained job metadata as well as each job's output.
            if len(self.jobs) >= 128:
                expired = next((k for k, v in self.jobs.items() if v.state != "running"), None)
                if expired is None:
                    raise ValueError("job capacity reached")
                self.jobs.pop(expired)
            self.jobs[job.job_id] = job
        threading.Thread(target=run_channel, args=(session, dict(body), job), daemon=True).start()
        return job

    def get(self, session_id):
        with self.lock:
            return self.sessions.get(session_id)

    def delete(self, session_id):
        with self.lock:
            session = self.sessions.pop(session_id, None)
            if session:
                key = (session.alias, session.shell, session.config_version)
                if self.alias_index.get(key) == session_id:
                    self.alias_index.pop(key, None)
        if session:
            session.close()
            return True
        return False

    def close_all(self):
        with self.lock:
            sessions = list(self.sessions.values())
            self.sessions.clear()
            self.alias_index.clear()
        for session in sessions:
            session.close()


class SSHRequestHandler(BaseHTTPRequestHandler):
    server_version = "SSHControlHTTP/1.0"

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - - [%s] %s\n" % (self.address_string(), self.log_date_time_string(), fmt % args))

    def _read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw)

    def _send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _error(self, status, message):
        self._send_json(status, {"error": message})

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/health":
            self._send_json(
                HTTPStatus.OK,
                {
                    "status": "ok",
                    "active_sessions": len(self.server.registry.list_sessions()),
                    "sessions": self.server.registry.list_sessions(),
                },
            )
            return
        match = re.fullmatch(r"/jobs/([^/]+)", path)
        if match:
            with self.server.registry.lock:
                job = self.server.registry.jobs.get(match.group(1))
            if job is None:
                self._error(HTTPStatus.NOT_FOUND, "job not found; restart/eviction loses history")
            else:
                self._send_json(HTTPStatus.OK, job.snapshot())
            return
        if path == "/connections":
            self._send_json(
                HTTPStatus.OK,
                {
                    "connections": [
                        public_connection(alias, item)
                        for alias, item in self.server.registry.connections.items()
                    ]
                },
            )
            return
        self._error(HTTPStatus.NOT_FOUND, "not found")

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            body = self._read_json()
            if not isinstance(body, dict):
                raise ValueError("JSON object required")
        except Exception as exc:
            self._error(HTTPStatus.BAD_REQUEST, f"invalid JSON body: {exc}")
            return

        if path == "/connections/reload":
            try:
                result = self.server.registry.reload()
                self._send_json(HTTPStatus.OK, result)
            except Exception:
                self._error(HTTPStatus.BAD_REQUEST, "invalid connection configuration; previous configuration retained")
            return

        match = re.fullmatch(r"/jobs/([^/]+)/wait", path)
        if match:
            with self.server.registry.lock:
                job = self.server.registry.jobs.get(match.group(1))
            if job is None:
                self._error(HTTPStatus.NOT_FOUND, "job not found; restart/eviction loses history")
                return
            try:
                result = job.wait(int(body.get("cursor", 0)), float(body.get("timeout", 30)), body.get("phase_version"))
                self._send_json(HTTPStatus.OK, result)
            except (TypeError, ValueError):
                self._error(HTTPStatus.BAD_REQUEST, "invalid wait parameters")
            return

        if path == "/sessions":
            alias = body.get("alias")
            if not alias:
                self._error(HTTPStatus.BAD_REQUEST, "alias is required")
                return
            shell = body.get("shell") or "/bin/bash"
            try:
                connect_timeout = int(body.get("connect_timeout", body.get("timeout", 10)))
                session, created = self.server.registry.get_or_create(alias, shell, connect_timeout, body.get("force_new", False))
            except KeyError as exc:
                self._error(HTTPStatus.NOT_FOUND, str(exc))
                return
            except Exception:
                self._error(HTTPStatus.BAD_GATEWAY, "failed to create SSH session")
                return
            payload = session.public_state()
            payload["created"] = created
            self._send_json(HTTPStatus.CREATED if created else HTTPStatus.OK, payload)
            return

        if path == "/shutdown":
            self._send_json(HTTPStatus.OK, {"status": "shutting_down"})
            threading.Thread(target=self.server.shutdown_server, daemon=True).start()
            return

        match = re.match(r"^/sessions/([^/]+)/(exec|jobs)$", path)
        if match:
            session_id = match.group(1)
            command = body.get("cmd")
            if not command:
                self._error(HTTPStatus.BAD_REQUEST, "cmd is required")
                return
            session = self.server.registry.get(session_id)
            if not session:
                self._error(HTTPStatus.NOT_FOUND, "session not found")
                return
            try:
                mode = body.get("mode", "shell")
                if mode not in ("shell", "exec"):
                    raise ValueError("mode must be shell or exec")
                independent = match.group(2) == "jobs" or mode == "exec" or body.get("sudo")
                if independent:
                    if match.group(2) == "exec":
                        body.setdefault("timeout", 30)
                    job = self.server.registry.start_job(session, body)
                    if match.group(2) == "jobs":
                        self._send_json(HTTPStatus.ACCEPTED, {"job_id": job.job_id, "state": "running"})
                        return
                    limit = float(body.get("timeout", 30))
                    with job.condition:
                        job.condition.wait_for(lambda: job.state != "running", timeout=limit + 1)
                    result = job.snapshot(0)
                    if result["state"] == "running":
                        result["error"] = "http_wait_timeout; query job_id; do not replay"
                else:
                    if any(k in body for k in ("cwd", "env", "stdin", "sudo_password")):
                        raise ValueError("cwd/env/stdin require mode=exec; shell state uses shell commands")
                    result = session.execute(command, timeout=float(body.get("timeout", 30)),
                                             allow_dangerous=self.server.registry.allow_dangerous)
            except PermissionError:
                self._error(HTTPStatus.FORBIDDEN, "dangerous command rejected")
                return
            except (ValueError, TypeError):
                self._error(HTTPStatus.BAD_REQUEST, "invalid execution options")
                return
            status = HTTPStatus.OK if result.get("exit_code", -1) != -2 else HTTPStatus.FORBIDDEN
            self._send_json(status, result)
            return

        self._error(HTTPStatus.NOT_FOUND, "not found")

    def do_DELETE(self):
        path = urlparse(self.path).path
        match = re.match(r"^/sessions/([^/]+)$", path)
        if not match:
            self._error(HTTPStatus.NOT_FOUND, "not found")
            return
        deleted = self.server.registry.delete(match.group(1))
        if not deleted:
            self._error(HTTPStatus.NOT_FOUND, "session not found")
            return
        self._send_json(HTTPStatus.OK, {"deleted": True})


class SSHHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, server_address, handler_class, registry):
        super().__init__(server_address, handler_class)
        self.registry = registry

    def shutdown_server(self):
        self.registry.close_all()
        self.shutdown()


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--allow-nonlocal-bind", action="store_true")
    parser.add_argument("--allow-dangerous", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.bind not in ("127.0.0.1", "localhost", "::1") and not args.allow_nonlocal_bind:
        print(
            json.dumps(
                {
                    "error": "Refusing to bind outside localhost without --allow-nonlocal-bind",
                    "bind": args.bind,
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        sys.exit(2)

    connections = load_connections()
    registry = SessionRegistry(connections, allow_dangerous=args.allow_dangerous)
    server = SSHHTTPServer((args.bind, args.port), SSHRequestHandler, registry)

    def handle_signal(signum, _frame):
        print(f"received signal {signum}, shutting down", file=sys.stderr)
        threading.Thread(target=server.shutdown_server, daemon=True).start()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    print(
        json.dumps(
            {
                "status": "listening",
                "bind": args.bind,
                "port": args.port,
                "connections": sorted(connections.keys()),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    try:
        server.serve_forever()
    finally:
        registry.close_all()
        server.server_close()


if __name__ == "__main__":
    main()
