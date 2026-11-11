"""Independent SSH channels, bounded cursor-based jobs and detached remote jobs.

Two job kinds:
- attached: output streams over one SSH channel; the job ends if that channel,
  the Transport or this service goes away (sync exec, sudo with a password).
- detached (default for `jobs start`): the command runs under
  ~/.codex-ssh-jobs/codex-job on the remote host (scripts/remote_job.sh), with
  output in plain files. It survives SSH drops, service restarts and Mac sleep,
  and can be inspected or cancelled with native `ssh` as well.
"""
import codecs
import math
import re
import shlex
import threading
import time
import uuid
from collections import deque
from pathlib import Path

OUTPUT_LIMIT = 1024 * 1024
POLL_CHUNK = 1024 * 1024
REMOTE_JOB_SCRIPT = (Path(__file__).resolve().parent / "remote_job.sh").read_text(encoding="utf-8")
REMOTE_ROOT = "~/.codex-ssh-jobs"
JOB_ID_RE = re.compile(r"^[0-9a-f]{8,64}$")


class Job:
    def __init__(self, job_id=None, detached=False, alias=None):
        self.job_id = job_id or uuid.uuid4().hex
        self.started = time.monotonic()
        self.started_wall = time.time()
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
        self.cancel_event = threading.Event()
        self.log_path = None
        self.on_finish = None
        # Detached-job bookkeeping.
        self.detached = detached
        self.alias = alias
        self.attached = False
        self.restored = False
        self.needs_resync = False
        self.offsets = [0, 0]
        self.decoders = [codecs.getincrementaldecoder("utf-8")("replace") for _ in range(2)]
        self.poll_lock = threading.Lock()

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
        if self.on_finish:
            self.on_finish(self)

    def set_attached(self, attached, error=None):
        with self.condition:
            self.attached = attached
            if error is not None:
                self.error = error
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
            if self.log_path:
                result['log_path'] = self.log_path
            for stream in ("stdout", "stderr"):
                value = "".join(e[2] for e in events if e[1] == stream)
                result[stream] = value if cursor is not None else value[-16384:]
            result["tail_limit"] = 16384 if cursor is None else None
            result["tail_truncated"] = cursor is None and any(
                sum(len(e[2]) for e in events if e[1] == stream) > 16384
                for stream in ("stdout", "stderr"))
            if self.detached:
                result.update(detached=True, alias=self.alias, attached=self.attached,
                              remote_dir=f"{REMOTE_ROOT}/{self.job_id}")
                if self.restored:
                    result["restored"] = True
            return result

    def summary(self):
        return dict(job_id=self.job_id, state=self.state, exit_code=self.exit_code,
                    detached=self.detached, alias=self.alias, error=self.error,
                    started_at=int(self.started_wall))

    def wait(self, cursor=0, timeout=30, phase_version=None):
        with self.condition:
            version = self.phase_version if phase_version is None else phase_version
            self.condition.wait_for(
                lambda: (self.state != "running" or self.phase_version != version
                         or (self.detached and not self.attached)),
                timeout=max(0, min(float(timeout), 50)))
            return self.snapshot(cursor)


# ------------------------------------------------------------ command building

def validate_body(body):
    command = body["cmd"]
    if not isinstance(command, str):
        raise ValueError("cmd must be text")
    for field in ("stdin", "cwd", "sudo_password"):
        if field in body and not isinstance(body[field], str):
            raise ValueError(field + " must be text")
    if "sudo_password" in body and (not body.get("sudo") or "\n" in body["sudo_password"]
                                    or "\r" in body["sudo_password"]):
        raise ValueError("invalid sudo password options")
    if "timeout" in body and body["timeout"] is not None:
        timeout = float(body["timeout"])
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be positive and finite")
    env = body.get("env") or {}
    if not isinstance(env, dict):
        raise ValueError("env must be an object")
    if any(not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key) for key in env):
        raise ValueError("invalid environment variable name")


def script_body(body):
    """The business script with explicit cwd/env applied."""
    validate_body(body)
    command = body["cmd"]
    env = body.get("env") or {}
    if env:
        command = "export " + " ".join(f"{k}={shlex.quote(str(v))}" for k, v in env.items()) + "\n" + command
    if body.get("cwd"):
        command = "cd -- " + shlex.quote(body["cwd"]) + " || exit\n" + command
    return command


def command_line(body, ready, prompt="__CODEX_PASSWORD_VALIDATE__"):
    command = script_body(body)
    if not body.get("sudo"):
        return "/bin/sh -c " + shlex.quote(command)
    # Script is an argument, never stdin. The privileged wrapper announces success
    # before business input is sent, even when sudo ignores stdin (NOPASSWD/cache).
    wrapper = f"printf '%s' {shlex.quote(ready)} >&2; exec /bin/sh -c {shlex.quote(command)}"
    flags = "-S -p " + shlex.quote(prompt) if body.get("sudo_password") is not None else "-n"
    return "sudo " + flags + " -- /bin/sh -c " + shlex.quote(wrapper)


def detached_script(body):
    command = script_body(body)
    if body.get("sudo_password") is not None:
        raise ValueError("sudo with a password needs attached mode")
    if body.get("sudo"):
        return "exec sudo -n -- /bin/sh -c " + shlex.quote(command)
    return command


# ------------------------------------------------------------ attached channels

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

    def flush_and_finish(state, error):
        for stream, decoder in decoders.items():
            emit(stream, decoder.decode(b"", final=True))
        emit("stderr", pending_err.replace(prompt, "").replace(ready, ""))
        for stream in pending:
            emit(stream, "", final=True)
        job.finish(state, error=error)

    try:
        transport = session.client.get_transport()
        if not transport or not transport.is_active():
            flush_and_finish("unknown", "ssh_disconnected")
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
            got = False
            # Fair bounded reads prevent either stream from starving the other.
            for stream, available, receive in (("stdout", channel.recv_ready, channel.recv),
                                                ("stderr", channel.recv_stderr_ready, channel.recv_stderr)):
                if not available():
                    continue
                got = True
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
            if job.cancel_event.is_set():
                flush_and_finish("cancelled", "cancelled_by_client; remote process may still be running")
                return
            if (not transport.is_active() or channel.closed) and not channel.recv_ready() and not channel.recv_stderr_ready():
                flush_and_finish("unknown", "ssh_disconnected")
                return
            if deadline and time.monotonic() >= deadline:
                flush_and_finish("unknown", "execution_timeout")
                return
            if not got:
                time.sleep(0.01)
    except Exception:
        # Do not expose exception text: a server/proxy may include request data.
        flush_and_finish("unknown", "ssh_channel_error")
    finally:
        if channel is not None:
            channel.close()
        password = None
        body.pop("sudo_password", None)


def remote_exec(session, command, stdin=b"", timeout=60):
    """Run one command on a fresh channel. Returns (exit_code, stdout_bytes, stderr_bytes)."""
    transport = session.client.get_transport()
    if not transport or not transport.is_active():
        raise ConnectionError("ssh_disconnected")
    channel = transport.open_session(timeout=10)
    try:
        channel.settimeout(0.2)
        channel.exec_command(command)
        if stdin:
            channel.sendall(stdin)
        channel.shutdown_write()
        out, err = bytearray(), bytearray()
        deadline = time.monotonic() + timeout
        while True:
            got = False
            while channel.recv_ready():
                out += channel.recv(65536)
                got = True
            while channel.recv_stderr_ready():
                err += channel.recv_stderr(65536)
                got = True
            if channel.exit_status_ready() and not channel.recv_ready() and not channel.recv_stderr_ready():
                return channel.recv_exit_status(), bytes(out), bytes(err)
            if channel.closed or not transport.is_active():
                raise ConnectionError("ssh_disconnected")
            if time.monotonic() >= deadline:
                raise TimeoutError("remote_exec_timeout")
            if not got:
                time.sleep(0.005)
    finally:
        channel.close()


def job_tool(*args):
    """Command line running remote_job.sh without depending on the installed copy."""
    return ("/bin/sh -c " + shlex.quote(REMOTE_JOB_SCRIPT) + " codex-job "
            + " ".join(shlex.quote(str(a)) for a in args))


INSTALL_COMMAND = (
    "/bin/sh -c " + shlex.quote(
        'umask 077; r="$HOME/.codex-ssh-jobs"; mkdir -p "$r" && cat > "$r/codex-job.tmp" '
        '&& chmod 700 "$r/codex-job.tmp" && mv "$r/codex-job.tmp" "$r/codex-job"'))


# ------------------------------------------------------------ detached jobs

def start_detached(session, body, job):
    if getattr(session, "is_powershell", False):
        raise ValueError("detached jobs need a POSIX remote; use attached=true with PowerShell")
    script = detached_script(body)
    code, _out, _err = remote_exec(session, INSTALL_COMMAND, stdin=REMOTE_JOB_SCRIPT.encode(), timeout=30)
    if code != 0:
        raise RuntimeError("detached_install_failed")
    code, _out, err = remote_exec(session, job_tool("start", job.job_id, script),
                                  stdin=body.get("stdin", "").encode(), timeout=30)
    if code != 0:
        raise RuntimeError("detached_start_failed: " + err.decode("utf-8", "replace")[-300:])


def poll_detached(job, get_session):
    """Follow a detached job until it ends or the connection drops.

    Byte offsets into the remote stdout/stderr files are the source of truth, so
    a dropped connection or a service restart resumes without losing output.
    """
    if not job.poll_lock.acquire(blocking=False):
        return  # another poller is active
    was_finished = job.state != "running"
    with job.condition:
        job.attached = True
        if not was_finished:
            job.error = None
        job.condition.notify_all()
    try:
        session = get_session(job.alias)
        if job.needs_resync:
            code, out, _err = remote_exec(session, job_tool("size", job.job_id), timeout=30)
            if code == 3:
                if was_finished:
                    job.set_attached(False, error="remote output pruned (job directory removed)")
                else:
                    job.finish("unknown", error="remote_job_dir_missing")
                return
            sizes = [int(x) for x in out.split()[:2]]
            job.offsets = [max(0, s - OUTPUT_LIMIT) for s in sizes]
            job.needs_resync = False
        interval = 0.2
        while True:
            code, out, err = remote_exec(
                session, job_tool("poll", job.job_id, job.offsets[0], job.offsets[1], POLL_CHUNK), timeout=60)
            for index, (stream, data) in enumerate((("stdout", out), ("stderr", err))):
                job.offsets[index] += len(data)
                job.append(stream, job.decoders[index].decode(data))
            more = len(out) >= POLL_CHUNK or len(err) >= POLL_CHUNK
            if code == 0:
                if more:
                    continue
                interval = 0.2 if (out or err) else min(interval * 1.5, 2.0)
                time.sleep(interval)
                continue
            if code == 11 or (code == 10 and more):
                continue
            for index, stream in enumerate(("stdout", "stderr")):
                job.append(stream, job.decoders[index].decode(b"", final=True))
            if code == 10:
                ec_code, ec_out, _ = remote_exec(session, job_tool("exit-code", job.job_id), timeout=30)
                exit_code = int(ec_out.strip()) if ec_code == 0 and ec_out.strip().isdigit() else None
                job.finish("completed", exit_code)
            elif code == 13:
                job.finish("cancelled", error="cancelled")
            elif code == 12:
                job.finish("unknown", error="remote_process_vanished (killed or host rebooted)")
            elif code == 3:
                if was_finished:
                    job.set_attached(False, error="remote output pruned (job directory removed)")
                else:
                    job.finish("unknown", error="remote_job_dir_missing")
            else:
                raise RuntimeError("unexpected poll status")
            return
    except Exception as exc:
        code = getattr(exc, "code", None) or type(exc).__name__
        if job.state == "running":
            job.set_attached(False, error=f"detached job not attached ({code}); it keeps running "
                                          "remotely; query the job again to reattach")
    finally:
        job.set_attached(False)
        job.poll_lock.release()


def cancel_detached(session, job):
    code, out, err = remote_exec(session, job_tool("cancel", job.job_id), timeout=30)
    return code, (out + err).decode("utf-8", "replace").strip()


def native_hint(alias, job_id):
    if not alias or not re.fullmatch(r"[A-Za-z0-9._@-]+", alias):
        return None
    return f"ssh {alias} '{REMOTE_ROOT}/codex-job status {job_id}'"
