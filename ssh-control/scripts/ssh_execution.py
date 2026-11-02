"""Independent SSH channels and bounded, cursor-based in-memory jobs."""
import codecs
import math
import re
import shlex
import threading
import time
import uuid
from collections import deque

OUTPUT_LIMIT = 1024 * 1024


class Job:
    def __init__(self):
        self.job_id = uuid.uuid4().hex
        self.started = time.monotonic()
        self.finished = None
        self.state = "running"
        self.exit_code = None
        self.error = None
        self.phase = None
        self.phase_version = 0
        self.events = deque()
        self.size = 0
        self.cursor = 0
        self.condition = threading.Condition()
        self.phase_buffer = ""

    def append(self, stream, text):
        if not text:
            return
        with self.condition:
            self.cursor += 1
            self.events.append((self.cursor, stream, text))
            self.size += len(text)
            while self.size > OUTPUT_LIMIT and self.events:
                self.size -= len(self.events.popleft()[2])
            if stream == "stdout":
                self.phase_buffer += text
                lines = self.phase_buffer.split("\n")
                self.phase_buffer = lines.pop()[-4096:]
                for line in lines:
                    if line.startswith("__CODEX_PHASE__:"):
                        self.phase = line[len("__CODEX_PHASE__:"):][:1024]
                        self.phase_version += 1
            self.condition.notify_all()

    def finish(self, state, code=None, error=None):
        with self.condition:
            self.state, self.exit_code, self.error = state, code, error
            self.finished = time.monotonic()
            self.condition.notify_all()

    def snapshot(self, cursor=None):
        with self.condition:
            base = self.events[0][0] - 1 if self.events else self.cursor
            events = [e for e in self.events if cursor is None or e[0] > cursor]
            result = dict(job_id=self.job_id, state=self.state,
                          duration_ms=int(((self.finished or time.monotonic()) - self.started) * 1000),
                          exit_code=self.exit_code, error=self.error, phase=self.phase,
                          phase_version=self.phase_version, cursor=self.cursor,
                          dropped_before=base, truncated=(base > (cursor or 0)))
            for stream in ("stdout", "stderr"):
                value = "".join(e[2] for e in events if e[1] == stream)
                result[stream] = value if cursor is not None else value[-16384:]
            result["tail_limit"] = 16384 if cursor is None else None
            result["tail_truncated"] = cursor is None and any(
                sum(len(e[2]) for e in events if e[1] == stream) > 16384
                for stream in ("stdout", "stderr"))
            return result

    def wait(self, cursor=0, timeout=30, phase_version=None):
        with self.condition:
            version = self.phase_version if phase_version is None else phase_version
            self.condition.wait_for(lambda: self.state != "running" or self.phase_version != version,
                                    timeout=max(0, min(float(timeout), 50)))
            return self.snapshot(cursor)


def command_line(body, ready, prompt="__CODEX_PASSWORD_VALIDATE__"):
    command = body["cmd"]
    if not isinstance(command, str):
        raise ValueError("cmd must be text")
    for field in ("stdin", "cwd", "sudo_password"):
        if field in body and not isinstance(body[field], str):
            raise ValueError(field + " must be text")
    if "sudo_password" in body and (not body.get("sudo") or "\n" in body["sudo_password"] or "\r" in body["sudo_password"]):
        raise ValueError("invalid sudo password options")
    if "timeout" in body:
        timeout = float(body["timeout"])
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be positive and finite")
    env = body.get("env") or {}
    if not isinstance(env, dict):
        raise ValueError("env must be an object")
    if any(not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key) for key in env):
        raise ValueError("invalid environment variable name")
    if env:
        command = "export " + " ".join(f"{k}={shlex.quote(str(v))}" for k, v in env.items()) + "\n" + command
    if body.get("cwd"):
        command = "cd -- " + shlex.quote(body["cwd"]) + " || exit\n" + command
    if not body.get("sudo"):
        return "/bin/sh -c " + shlex.quote(command)
    # Script is an argument, never stdin. The privileged wrapper announces success
    # before business input is sent, even when sudo ignores stdin (NOPASSWD/cache).
    wrapper = f"printf '%s' {shlex.quote(ready)} >&2; exec /bin/sh -c {shlex.quote(command)}"
    flags = "-S -p " + shlex.quote(prompt) if body.get("sudo_password") is not None else "-n"
    return "sudo " + flags + " -- /bin/sh -c " + shlex.quote(wrapper)


def run_channel(session, body, job):
    password = body.pop("sudo_password", None)
    channel = None
    ready = "__CODEX_READY_" + uuid.uuid4().hex + "__"
    prompt = "__CODEX_PASSWORD_" + uuid.uuid4().hex + "__"
    authenticated = not body.get("sudo")
    password_sent = False
    input_sent = False
    pending_err = ""
    decoders = {s: codecs.getincrementaldecoder("utf-8")("replace") for s in ("stdout", "stderr")}
    # Retain enough characters to redact secrets even across network packets.
    pending = {"stdout": "", "stderr": ""}

    def emit(stream, text, final=False):
        pending[stream] += text
        value = pending[stream]
        if password:
            value = value.replace(password, "[REDACTED]")
        hold = max(0, len(password or "") - 1) if not final else 0
        split = max(0, len(value) - hold)
        job.append(stream, value[:split])
        pending[stream] = value[split:]

    def unknown(error):
        for stream, decoder in decoders.items():
            emit(stream, decoder.decode(b"", final=True))
        emit("stderr", pending_err.replace(prompt, "").replace(ready, ""))
        for stream in pending:
            emit(stream, "", final=True)
        job.finish("unknown", error=error)

    try:
        transport = session.client.get_transport()
        if not transport or not transport.is_active():
            unknown("ssh_disconnected")
            return
        channel = transport.open_session(timeout=10)
        channel.settimeout(0.2)
        command_body = dict(body)
        if password is not None:
            command_body["sudo_password"] = password
        channel.exec_command(command_line(command_body, ready, prompt))
        command_body.pop("sudo_password", None)
        deadline = time.monotonic() + float(body["timeout"]) if body.get("timeout") else None
        while True:
            # Fair bounded reads prevent either stream from starving the other.
            for stream, available, receive in (("stdout", channel.recv_ready, channel.recv),
                                                ("stderr", channel.recv_stderr_ready, channel.recv_stderr)):
                if not available():
                    continue
                text = decoders[stream].decode(receive(32768))
                if stream == "stderr" and not authenticated:
                    pending_err += text
                    if prompt in pending_err:
                        pending_err = pending_err.replace(prompt, "")
                        if password is not None and not password_sent:
                            channel.sendall((password + "\n").encode())
                            password_sent = True
                        else:
                            channel.shutdown_write()
                    if ready in pending_err:
                        pending_err = pending_err.replace(ready, "")
                        authenticated = True
                    if authenticated:
                        emit(stream, pending_err)
                        pending_err = ""
                    elif len(pending_err) > 8192:
                        emit(stream, pending_err[:-len(prompt)])
                        pending_err = pending_err[-len(prompt):]
                else:
                    emit(stream, text)
            if authenticated and not input_sent:
                # A separate writer prevents a command that writes before reading
                # a large stdin from deadlocking output drainage.
                def send_input():
                    try:
                        channel.sendall(body.get("stdin", "").encode())
                        channel.shutdown_write()
                    except Exception:
                        pass  # channel result/disconnect determines the outcome
                threading.Thread(target=send_input, daemon=True).start()
                input_sent = True
            if channel.exit_status_ready() and not channel.recv_ready() and not channel.recv_stderr_ready():
                code = channel.recv_exit_status()
                for stream in decoders:
                    emit(stream, decoders[stream].decode(b"", final=True))
                emit("stderr", pending_err.replace(prompt, "").replace(ready, ""))
                for stream in pending:
                    emit(stream, "", final=True)
                if code == -1:
                    job.finish("unknown", error="ssh_disconnected")
                elif body.get("sudo") and not authenticated:
                    job.finish("failed", code, "sudo_auth_failed" if password is not None else "sudo_password_required")
                else:
                    job.finish("completed", code)
                return
            if (not transport.is_active() or channel.closed) and not channel.recv_ready() and not channel.recv_stderr_ready():
                unknown("ssh_disconnected")
                return
            if deadline and time.monotonic() >= deadline:
                unknown("execution_timeout")
                return
            time.sleep(0.01)
    except Exception:
        # Do not expose exception text: a server/proxy may include request data.
        unknown("ssh_channel_error")
    finally:
        if channel is not None:
            channel.close()
        password = None
        body.pop("sudo_password", None)
