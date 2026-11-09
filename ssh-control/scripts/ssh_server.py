# Run with: uv run --with paramiko python scripts/ssh_server.py --bind 127.0.0.1 --port 47622
r"""
Persistent SSH HTTP service for ssh-control.

Sessions keep one authenticated SSH Transport per alias plus a persistent shell.
Aliases come from references/connections.json and every concrete Host in
~/.ssh/config (see ssh_connect.py). Host keys are checked against the same
known_hosts as native ssh. Detached jobs live on the remote host under
~/.codex-ssh-jobs and survive service restarts (see ssh_execution.py).

It listens on localhost and does not expose private key contents.
"""

import argparse
import codecs
import hmac
import json
import os
import re
import shlex
import signal
import sys
import threading
import time
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from ssh_connect import ConnectError, connect, public_connection, resolve_all
from ssh_execution import (JOB_ID_RE, OUTPUT_LIMIT, Job, cancel_detached, native_hint,
                           poll_detached, run_channel, start_detached, validate_body)
from ssh_safety import dangerous_reason
from ssh_token import ensure_token
import ssh_mcp
import ssh_sftp

SKILL_DIR = Path(__file__).resolve().parents[1]
STATE_DIR = Path(os.environ.get("SSH_CONTROL_STATE_DIR", SKILL_DIR / "state" / "jobs")).expanduser()
DEFAULT_PORT = 47622
MAX_JOBS = 128
LOCAL_HOSTNAMES = {"127.0.0.1", "localhost", "::1"}


class PersistentShellSession:
    def __init__(self, session_id, alias, config, shell="/bin/bash", connect_timeout=10):
        self.session_id = session_id
        self.alias = alias
        self.config = config
        self.shell = shell
        self.is_powershell = shell.lower().split()[0] in (
            "powershell", "powershell.exe", "pwsh", "pwsh.exe")
        self.created_at = time.time()
        self.last_used_at = None
        self.lock = threading.Lock()
        self.channel = None
        self.client, self.proxy = connect(config, timeout=connect_timeout)
        self._open_shell()

    def _open_shell(self):
        transport = self.client.get_transport()
        self.channel = transport.open_session(timeout=10)
        self.channel.settimeout(0.2)
        self.channel.exec_command(self.shell)
        deadline = time.time() + 0.5
        while time.time() < deadline:
            while self.channel.recv_ready():
                self.channel.recv(65535)
            while self.channel.recv_stderr_ready():
                self.channel.recv_stderr(65535)
            time.sleep(0.05)

    def transport_active(self):
        transport = self.client.get_transport()
        return bool(transport and transport.is_active())

    def shell_alive(self):
        return bool(self.channel and not self.channel.closed and not self.channel.exit_status_ready())

    def is_connected(self):
        return self.transport_active() and self.shell_alive()

    def _payload(self, command, marker):
        if self.is_powershell:
            return (
                "$global:LASTEXITCODE = 0\n"
                f"{command}\n"
                "$__codex_success = $?\n"
                "$__codex_status = if ($__codex_success) { "
                "[int]$global:LASTEXITCODE } elseif ($global:LASTEXITCODE -ne 0) { "
                "[int]$global:LASTEXITCODE } else { 1 }\n"
                f"[Console]::Error.WriteLine(\"{marker}ERR\")\n"
                f"[Console]::Out.WriteLine(\"`n{marker}:{{0}}\" -f $__codex_status)\n"
            )
        # The command is one quoted eval argument: an unbalanced quote or heredoc
        # cannot swallow the marker lines, and stdin is /dev/null so programs that
        # read stdin (apt prompts, cat, python -) cannot consume the protocol.
        return (
            f"eval {shlex.quote(command)} </dev/null\n"
            "__codex_status=$?\n"
            f"printf '{marker}ERR\\n' >&2\n"
            f"printf '\\n{marker}:%s:%s\\n' \"$__codex_status\" \"$PWD\"\n"
        )

    def execute(self, command, timeout=30):
        with self.lock:
            started = time.time()
            if not self.transport_active():
                return {"command": command, "stdout": "", "stderr": "SSH transport is disconnected",
                        "exit_code": -1, "duration_ms": 0, "error": "ssh_disconnected"}
            restarted = False
            if not self.shell_alive():
                self._open_shell()
                restarted = True

            marker = f"__CODEX_SSH_DONE_{uuid.uuid4().hex}__"
            try:
                self.channel.sendall(self._payload(command, marker))
            except Exception:
                return {"command": command, "stdout": "", "stderr": "SSH write failed",
                        "exit_code": -1, "duration_ms": int((time.time() - started) * 1000),
                        "error": "ssh_write_failed"}

            # POSIX shells append ":$PWD" (PowerShell does not); the window covers PATH_MAX.
            done_re = re.compile(re.escape(marker) + r":(-?\d+)(?::([^\r\n]*))?\r?\n")
            err_re = re.compile(re.escape(marker) + r"ERR\r?\n")
            window = len(marker) + 32 + 4096
            dec_out = codecs.getincrementaldecoder("utf-8")("replace")
            dec_err = codecs.getincrementaldecoder("utf-8")("replace")
            out, err = "", ""
            out_scan = err_scan = 0
            dropped = [0, 0]
            exit_code = None
            cwd = None
            stderr_done = False
            deadline = started + timeout
            while time.time() < deadline:
                got = False
                while self.channel.recv_ready():
                    out += dec_out.decode(self.channel.recv(65535))
                    got = True
                while self.channel.recv_stderr_ready():
                    err += dec_err.decode(self.channel.recv_stderr(65535))
                    got = True
                if exit_code is None and got:
                    match = done_re.search(out, max(0, out_scan - window))
                    if match:
                        exit_code = int(match.group(1))
                        cwd = match.group(2)
                        out = out[:match.start()]
                        if out.endswith("\n"):
                            out = out[:-1]  # newline printed before the marker
                    else:
                        out_scan = len(out)
                if not stderr_done and got:
                    match = err_re.search(err, max(0, err_scan - window))
                    if match:
                        stderr_done = True
                        err = err[:match.start()] + err[match.end():]
                    else:
                        err_scan = len(err)
                # Keep the newest output only; marker search uses a sliding window.
                if len(out) > OUTPUT_LIMIT:
                    cut = len(out) - OUTPUT_LIMIT
                    dropped[0] += cut
                    out, out_scan = out[cut:], max(0, out_scan - cut)
                if len(err) > OUTPUT_LIMIT:
                    cut = len(err) - OUTPUT_LIMIT
                    dropped[1] += cut
                    err, err_scan = err[cut:], max(0, err_scan - cut)
                if exit_code is not None and stderr_done:
                    break
                if not self.shell_alive():
                    break
                if not got:
                    time.sleep(0.01)

            out += dec_out.decode(b"", final=True)
            err += dec_err.decode(b"", final=True)
            self.last_used_at = time.time()
            result = {"command": command, "stdout": out, "stderr": err,
                      "exit_code": exit_code, "duration_ms": int((time.time() - started) * 1000)}
            if cwd:
                result["cwd"] = cwd
            if dropped[0] or dropped[1]:
                result["output_truncated"] = {"stdout_chars_dropped": dropped[0],
                                              "stderr_chars_dropped": dropped[1]}
            if restarted:
                result["shell_restarted"] = "previous shell had exited; cwd/env were reset"

            if exit_code is not None and stderr_done:
                return result
            if not self.shell_alive():
                status = self.channel.recv_exit_status() if self.channel.exit_status_ready() else None
                result.update(exit_code=status if status is not None else -1,
                              error="shell_exited; the next call starts a fresh shell (cwd/env reset)")
                return result
            try:
                self.channel.close()
            except Exception:
                pass
            result.update(exit_code=-1, error=f"timeout after {timeout}s; shell closed, outcome uncertain")
            return result

    def close(self):
        try:
            if self.channel is not None and not self.channel.closed:
                self.channel.close()
        finally:
            self.client.close()
            if self.proxy is not None:
                try:
                    self.proxy.close()
                except Exception:
                    pass

    def public_state(self):
        return {
            "session_id": self.session_id,
            "alias": self.alias,
            "host": self.config.get("host"),
            "username": self.config.get("username"),
            "shell": self.shell,
            "connected": self.transport_active(),
            "shell_alive": self.shell_alive(),
            "created_at": self.created_at,
            "last_used_at": self.last_used_at,
            "config_version": getattr(self, "config_version", 1),
        }


class SessionRegistry:
    def __init__(self, allow_dangerous=False):
        self.connections = resolve_all()
        self.allow_dangerous = allow_dangerous
        self.lock = threading.Lock()
        self.sessions = {}
        self.alias_index = {}
        self.versions = {alias: 1 for alias in self.connections}
        self.reload_lock = threading.Lock()
        self.jobs = {}
        self._restore_jobs()

    # ---------------------------------------------------------------- sessions

    def prune_dead(self):
        """Close and forget sessions whose SSH Transport is gone."""
        with self.lock:
            dead = [s for s in self.sessions.values() if not s.transport_active()]
            for session in dead:
                self.sessions.pop(session.session_id, None)
                key = (session.alias, session.shell, session.config_version)
                if self.alias_index.get(key) == session.session_id:
                    self.alias_index.pop(key, None)
        for session in dead:
            try:
                session.close()
            except Exception:
                pass
        return len(dead)

    def list_sessions(self):
        self.prune_dead()
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
            connections = resolve_all()
            for item in connections.values():
                if not item.get("host") or not item.get("username"):
                    raise ValueError("missing connection field")
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
        self.prune_dead()
        with self.lock:
            if alias not in self.connections:
                raise KeyError("unknown connection alias")
            config = dict(self.connections[alias])
            version = self.versions[alias]
            key = (alias, shell, version)
            existing = self.sessions.get(self.alias_index.get(key))
            if not force_new and existing and existing.transport_active():
                return existing, False
        # SSH connect/open/startup must never hold the registry lock.
        session = PersistentShellSession(uuid.uuid4().hex, alias, config, shell, connect_timeout)
        session.config_version = version
        with self.lock:
            winner = self.sessions.get(self.alias_index.get(key))
            if not force_new and winner and winner.transport_active():
                reuse = winner
            else:
                self.sessions[session.session_id] = session
                self.alias_index[key] = session.session_id
                reuse = None
        if reuse:
            session.close()
            return reuse, False
        return session, True

    def session_for_alias(self, alias):
        return self.get_or_create(alias)[0]

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

    # ---------------------------------------------------------------- jobs

    def check_command(self, command):
        if self.allow_dangerous:
            return None
        return dangerous_reason(command)

    def _add_job(self, job):
        with self.lock:
            if len(self.jobs) >= MAX_JOBS:
                expired = next((k for k, v in self.jobs.items() if v.state != "running"), None)
                if expired is None:
                    raise ValueError("job capacity reached")
                self.jobs.pop(expired)
                self._delete_record(expired)
            self.jobs[job.job_id] = job

    def get_job(self, job_id):
        with self.lock:
            return self.jobs.get(job_id)

    def start_job(self, session, body, detached=False):
        reason = self.check_command(body["cmd"])
        if reason:
            raise PermissionError(reason)
        validate_body(body)
        job = Job(detached=detached, alias=session.alias if detached else None)
        if detached:
            start_detached(session, body, job)   # raises before the job is registered
            job.on_finish = self._save_record
            self._add_job(job)
            self._save_record(job)
            threading.Thread(target=poll_detached, args=(job, self.session_for_alias), daemon=True).start()
            return job
        self._add_job(job)
        threading.Thread(target=run_channel, args=(session, dict(body), job), daemon=True).start()
        return job

    def ensure_attached(self, job):
        """Resume following a detached job (after a drop or a service restart)."""
        if not job.detached or job.attached:
            return
        if job.state == "running":
            threading.Thread(target=poll_detached, args=(job, self.session_for_alias), daemon=True).start()
            with job.condition:
                job.condition.wait_for(lambda: job.attached or job.state != "running", timeout=1)
        elif job.restored and not job.events:
            poll_detached(job, self.session_for_alias)   # fetch the output tail once

    def attach_job(self, alias, job_id):
        if not JOB_ID_RE.match(job_id):
            raise ValueError("invalid job id")
        existing = self.get_job(job_id)
        if existing:
            return existing
        with self.lock:
            known = alias in self.connections
        if not known:
            raise KeyError("unknown connection alias")
        job = Job(job_id=job_id, detached=True, alias=alias)
        job.restored = job.needs_resync = True
        job.on_finish = self._save_record
        self._add_job(job)
        self._save_record(job)
        return job

    def cancel_job(self, job):
        if job.state != "running":
            return {"job_id": job.job_id, "state": job.state, "detail": "already finished"}
        if job.detached:
            code, detail = cancel_detached(self.session_for_alias(job.alias), job)
            self.ensure_attached(job)
            return {"job_id": job.job_id, "requested": code == 0, "detail": detail}
        job.cancel_event.set()
        return {"job_id": job.job_id, "requested": True,
                "detail": "attached channel closed; the remote process may continue"}

    # Detached job records survive service restarts.
    def _save_record(self, job):
        if not job.detached:
            return
        try:
            STATE_DIR.mkdir(parents=True, exist_ok=True)
            record = dict(job_id=job.job_id, alias=job.alias, state=job.state,
                          exit_code=job.exit_code, error=job.error, started_at=job.started_wall)
            tmp = STATE_DIR / (job.job_id + ".tmp")
            tmp.write_text(json.dumps(record), encoding="utf-8")
            os.replace(tmp, STATE_DIR / (job.job_id + ".json"))
        except Exception:
            pass

    def _delete_record(self, job_id):
        try:
            (STATE_DIR / (job_id + ".json")).unlink()
        except Exception:
            pass

    def _restore_jobs(self):
        if not STATE_DIR.exists():
            return
        records = []
        for path in STATE_DIR.glob("*.json"):
            try:
                records.append(json.loads(path.read_text(encoding="utf-8")))
            except Exception:
                continue
        records.sort(key=lambda r: r.get("started_at", 0))
        for record in records[-MAX_JOBS:]:
            job_id = record.get("job_id", "")
            if not JOB_ID_RE.match(job_id):
                continue
            job = Job(job_id=job_id, detached=True, alias=record.get("alias"))
            job.started_wall = record.get("started_at", time.time())
            job.restored = job.needs_resync = True
            job.state = record.get("state", "running")
            job.exit_code = record.get("exit_code")
            job.error = record.get("error")
            if job.state != "running":
                job.finished = job.started
            job.on_finish = self._save_record
            self.jobs[job_id] = job
        for path in STATE_DIR.glob("*.json"):
            if path.stem not in self.jobs:
                path.unlink(missing_ok=True)


class SSHRequestHandler(BaseHTTPRequestHandler):
    server_version = "SSHControlHTTP/2.0"

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

    def _error(self, status, message, **extra):
        self._send_json(status, dict(error=message, **extra))

    @property
    def registry(self):
        return self.server.registry

    def _authorized(self, method):
        """Reject browsers (DNS rebinding, cross-site requests) and unknown local clients."""
        host = self.headers.get("Host", "")
        match = re.fullmatch(r"\[?([^\[\]]+?)\]?(?::(\d+))?", host)
        port = str(self.server.server_address[1])
        if (not match or match.group(1).lower() not in self.server.allowed_hosts
                or (match.group(2) and match.group(2) != port)):
            self._error(HTTPStatus.FORBIDDEN, "host_not_allowed")
            return False
        if self.headers.get("Origin") is not None:
            self._error(HTTPStatus.FORBIDDEN, "browser_requests_not_allowed")
            return False
        if method == "POST" and not (self.headers.get("Content-Type") or "").lower().startswith("application/json"):
            self._error(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "content_type_must_be_application_json")
            return False
        auth = self.headers.get("Authorization") or ""
        supplied = auth[7:].strip() if auth[:7].lower() == "bearer " else ""
        # Re-read every request: deleting .env rotates the token without a restart.
        if not supplied or not hmac.compare_digest(supplied.encode(), ensure_token().encode()):
            self._error(HTTPStatus.UNAUTHORIZED, "missing_or_invalid_token",
                        detail="token lives in the skill's .env; ssh_client.py and the MCP helper read it")
            return False
        return True

    def do_GET(self):
        if not self._authorized("GET"):
            return
        path = urlparse(self.path).path
        if path == "/mcp":   # no server-initiated SSE stream
            self.send_response(HTTPStatus.METHOD_NOT_ALLOWED)
            self.send_header("Allow", "POST")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if path == "/health":
            sessions = self.registry.list_sessions()
            self._send_json(HTTPStatus.OK, {"status": "ok", "active_sessions": len(sessions),
                                            "sessions": sessions})
            return
        if path == "/jobs":
            with self.registry.lock:
                jobs = [j.summary() for j in self.registry.jobs.values()]
            self._send_json(HTTPStatus.OK, {"jobs": jobs})
            return
        match = re.fullmatch(r"/jobs/([^/]+)", path)
        if match:
            job = self.registry.get_job(match.group(1))
            if job is None:
                self._error(HTTPStatus.NOT_FOUND, "job not found; use jobs attach for a detached job id")
                return
            self.registry.ensure_attached(job)
            self._send_json(HTTPStatus.OK, job.snapshot())
            return
        if path == "/connections":
            with self.registry.lock:
                items = list(self.registry.connections.values())
            self._send_json(HTTPStatus.OK, {"connections": [public_connection(c) for c in items]})
            return
        self._error(HTTPStatus.NOT_FOUND, "not found")

    def do_POST(self):
        if not self._authorized("POST"):
            return
        path = urlparse(self.path).path
        if path == "/mcp":
            self._handle_mcp()
            return
        try:
            body = self._read_json()
            if not isinstance(body, dict):
                raise ValueError("JSON object required")
        except Exception as exc:
            self._error(HTTPStatus.BAD_REQUEST, f"invalid JSON body: {exc}")
            return
        try:
            self._dispatch_post(path, body)
        except ConnectError as exc:
            self._error(HTTPStatus.BAD_GATEWAY, exc.code, detail=exc.message)
        except KeyError:
            self._error(HTTPStatus.NOT_FOUND, "unknown connection alias")
        except PermissionError as exc:
            self._error(HTTPStatus.FORBIDDEN, "dangerous command rejected",
                        reason=str(exc), detail="needs explicit user approval")
        except (ValueError, TypeError) as exc:
            self._error(HTTPStatus.BAD_REQUEST, "invalid request", detail=str(exc)[:300])
        except (ConnectionError, TimeoutError, RuntimeError, OSError) as exc:
            self._error(HTTPStatus.BAD_GATEWAY, "remote_operation_failed", detail=str(exc)[:300])

    def do_HEAD(self):
        # Reachability probes (e.g. `codex doctor`); reveals nothing, so no auth needed.
        self.send_response(HTTPStatus.METHOD_NOT_ALLOWED)
        self.send_header("Allow", "POST" if urlparse(self.path).path == "/mcp" else "GET, POST, DELETE")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _handle_mcp(self):
        """MCP streamable HTTP, JSON responses only (no SSE)."""
        try:
            message = self._read_json()
        except Exception:
            self._send_json(HTTPStatus.BAD_REQUEST, ssh_mcp.rpc_error(None, -32700, "parse error"))
            return
        response = self.server.mcp.handle(message)
        if response is None:   # notifications / responses only
            self.send_response(HTTPStatus.ACCEPTED)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        body = json.dumps(response, ensure_ascii=False).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _dispatch_post(self, path, body):
        if path == "/connections/reload":
            try:
                self._send_json(HTTPStatus.OK, self.registry.reload())
            except Exception:
                self._error(HTTPStatus.BAD_REQUEST,
                            "invalid connection configuration; previous configuration retained")
            return

        if path == "/jobs/attach":
            job = self.registry.attach_job(str(body.get("alias", "")), str(body.get("job_id", "")))
            self.registry.ensure_attached(job)
            self._send_json(HTTPStatus.OK, job.snapshot())
            return

        match = re.fullmatch(r"/jobs/([^/]+)/(wait|cancel)", path)
        if match:
            job = self.registry.get_job(match.group(1))
            if job is None:
                self._error(HTTPStatus.NOT_FOUND, "job not found; use jobs attach for a detached job id")
                return
            if match.group(2) == "cancel":
                self._send_json(HTTPStatus.OK, self.registry.cancel_job(job))
                return
            self.registry.ensure_attached(job)
            result = job.wait(int(body.get("cursor", 0)), float(body.get("timeout", 30)),
                              body.get("phase_version"))
            self._send_json(HTTPStatus.OK, result)
            return

        if path == "/sessions":
            alias = body.get("alias")
            if not alias:
                self._error(HTTPStatus.BAD_REQUEST, "alias is required")
                return
            shell = body.get("shell") or "/bin/bash"
            connect_timeout = int(body.get("connect_timeout", body.get("timeout", 10)))
            session, created = self.registry.get_or_create(alias, shell, connect_timeout,
                                                           body.get("force_new", False))
            payload = session.public_state()
            payload["created"] = created
            self._send_json(HTTPStatus.CREATED if created else HTTPStatus.OK, payload)
            return

        if path == "/shutdown":
            self._send_json(HTTPStatus.OK, {"status": "shutting_down"})
            threading.Thread(target=self.server.shutdown_server, daemon=True).start()
            return

        match = re.match(r"^/sessions/([^/]+)/(exec|jobs|sftp)$", path)
        if not match:
            self._error(HTTPStatus.NOT_FOUND, "not found")
            return
        session = self.registry.get(match.group(1))
        if not session:
            self._error(HTTPStatus.NOT_FOUND, "session not found or closed; create a new one by alias")
            return

        if match.group(2) == "sftp":
            direction = body.get("direction")
            local, remote = body.get("local"), body.get("remote")
            if direction not in ("upload", "download") or not local or not remote:
                raise ValueError("direction (upload|download), local and remote are required")
            if not os.path.isabs(os.path.expanduser(local)):
                raise ValueError("local path must be absolute")
            sftp = session.client.open_sftp()
            try:
                if direction == "upload":
                    result = ssh_sftp.upload(sftp, local, remote, bool(body.get("recursive")))
                else:
                    result = ssh_sftp.download(sftp, remote, local, bool(body.get("recursive")))
            finally:
                sftp.close()
            self._send_json(HTTPStatus.OK, result)
            return

        command = body.get("cmd")
        if not command:
            self._error(HTTPStatus.BAD_REQUEST, "cmd is required")
            return
        mode = body.get("mode", "shell")
        if mode not in ("shell", "exec"):
            raise ValueError("mode must be shell or exec")

        if match.group(2) == "jobs":
            detached = (not body.get("attached") and body.get("sudo_password") is None
                        and not session.is_powershell)
            job = self.registry.start_job(session, body, detached=detached)
            payload = {"job_id": job.job_id, "state": "running", "detached": detached}
            hint = native_hint(session.alias, job.job_id) if detached else None
            if hint:
                payload["native"] = hint
            self._send_json(HTTPStatus.ACCEPTED, payload)
            return

        if mode == "exec" or body.get("sudo"):
            body.setdefault("timeout", 30)
            job = self.registry.start_job(session, body)
            limit = float(body.get("timeout", 30))
            with job.condition:
                job.condition.wait_for(lambda: job.state != "running", timeout=limit + 1)
            result = job.snapshot(0)
            if result["state"] == "running":
                result["error"] = "http_wait_timeout; query job_id; do not replay"
            self._send_json(HTTPStatus.OK, result)
            return

        if any(k in body for k in ("cwd", "env", "stdin", "sudo_password")):
            raise ValueError("cwd/env/stdin require mode=exec; shell state uses shell commands")
        reason = self.registry.check_command(command)
        if reason:
            raise PermissionError(reason)
        self._send_json(HTTPStatus.OK, session.execute(command, timeout=float(body.get("timeout", 30))))

    def do_DELETE(self):
        if not self._authorized("DELETE"):
            return
        path = urlparse(self.path).path
        match = re.match(r"^/sessions/([^/]+)$", path)
        if not match:
            self._error(HTTPStatus.NOT_FOUND, "not found")
            return
        if not self.registry.delete(match.group(1)):
            self._error(HTTPStatus.NOT_FOUND, "session not found")
            return
        self._send_json(HTTPStatus.OK, {"deleted": True})


class SSHHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, server_address, handler_class, registry, allowed_hosts):
        super().__init__(server_address, handler_class)
        self.registry = registry
        self.mcp = ssh_mcp.MCPServer(registry)
        self.allowed_hosts = allowed_hosts

    def shutdown_server(self):
        self.registry.close_all()
        self.shutdown()


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--allow-nonlocal-bind", action="store_true")
    parser.add_argument("--allow-dangerous", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.bind not in ("127.0.0.1", "localhost", "::1") and not args.allow_nonlocal_bind:
        print(json.dumps({"error": "Refusing to bind outside localhost without --allow-nonlocal-bind",
                          "bind": args.bind}, ensure_ascii=False), file=sys.stderr)
        sys.exit(2)

    ensure_token()   # create <skill>/.env on first use
    registry = SessionRegistry(allow_dangerous=args.allow_dangerous)
    allowed_hosts = LOCAL_HOSTNAMES | {args.bind.lower()}
    server = SSHHTTPServer((args.bind, args.port), SSHRequestHandler, registry, allowed_hosts)

    def handle_signal(signum, _frame):
        print(f"received signal {signum}, shutting down", file=sys.stderr)
        threading.Thread(target=server.shutdown_server, daemon=True).start()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    print(json.dumps({"status": "listening", "bind": args.bind, "port": args.port,
                      "connections": sorted(registry.connections.keys()),
                      "restored_jobs": len(registry.jobs)}, ensure_ascii=False), flush=True)
    try:
        server.serve_forever()
    finally:
        registry.close_all()
        server.server_close()


if __name__ == "__main__":
    main()
