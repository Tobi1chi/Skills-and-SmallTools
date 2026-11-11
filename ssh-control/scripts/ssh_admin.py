"""A short-lived sudo shell tied to one authenticated SSH transport."""
import codecs
import re
import shlex
import socket
import subprocess
import threading
import time
import uuid

from paramiko import SSHException
from ssh_admin_output import AdminOutput
from ssh_execution import script_body

ADMIN_SECONDS = 15 * 60


class AdminSession:
    def __init__(self, channel, session, log_dir, log_keep):
        self.channel = channel
        self.session = session
        self.log_dir, self.log_keep = log_dir, log_keep
        self.lock = threading.Lock()
        self.closed = threading.Event()
        self.expires_mono = time.monotonic() + ADMIN_SECONDS
        self.expires_at = time.time() + ADMIN_SECONDS
        self.timer = threading.Timer(ADMIN_SECONDS, self.close)
        self.timer.daemon = True
        self.timer.start()

    @classmethod
    def open(cls, session, password, log_dir, log_keep):
        if password is not None and (not isinstance(password, str) or '\n' in password or '\r' in password):
            raise ValueError('invalid sudo password')
        transport = session.client.get_transport()
        if not transport or not transport.is_active():
            raise ConnectionError('ssh_disconnected')
        channel = transport.open_session(timeout=10)
        channel.settimeout(0.2)
        prompt = '__CODEX_SUDO_' + uuid.uuid4().hex + '__'
        ready = '__CODEX_ADMIN_' + uuid.uuid4().hex + '__'
        script = 'test "$(id -u)" = 0 || exit 126; printf %s ' + shlex.quote(ready) + ' >&2; exec /bin/sh'
        try:
            channel.exec_command('sudo -S -p ' + shlex.quote(prompt) + ' -- /bin/sh -c ' + shlex.quote(script))
            pending = ''
            sent = False
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if channel.recv_stderr_ready():
                    pending += channel.recv_stderr(8192).decode('utf-8', 'replace')
                    if ready in pending:
                        return cls(channel, session, log_dir, log_keep)
                    if prompt in pending:
                        if sent or not password:
                            raise PermissionError('sudo_auth_failed')
                        channel.sendall((password + '\n').encode())
                        password = None
                        sent = True
                        pending = ''
                    pending = pending[-16384:]
                if channel.recv_ready():
                    channel.recv(8192)
                if channel.exit_status_ready() or channel.closed or not transport.is_active():
                    raise PermissionError('sudo_auth_failed')
                time.sleep(0.01)
            raise TimeoutError('sudo_auth_timeout')
        except BaseException:
            channel.close()
            raise
        finally:
            password = None

    def active(self):
        return (not self.closed.is_set() and time.monotonic() < self.expires_mono
                and not self.channel.closed and not self.channel.exit_status_ready())

    def close(self):
        if not self.closed.is_set():
            self.closed.set()
            self.timer.cancel()
            self.channel.close()

    def run(self, body, job):
        with self.lock:
            if job.cancel_event.is_set():
                job.finish('cancelled', error='admin_job_cancelled_before_start')
                return
            if not self.active():
                job.finish('failed', error='admin_session_expired')
                return
            marker = '__CODEX_ADMIN_DONE_' + uuid.uuid4().hex + '__'
            err_marker = marker + '_ERR'
            script = script_body(body)
            stdin = body.get('stdin')
            if '\0' in script or (stdin is not None and '\0' in stdin):
                job.finish('failed', error='NUL is unsupported in admin shell input')
                return
            output = None
            try:
                output = AdminOutput(self.session, job, self.log_dir, self.log_keep)
                output.log.record({'job_id': job.job_id, 'host': self.session.alias,
                                   'command': body['cmd'], 'cwd': body.get('cwd')})
                directory = output.start()
            except (OSError, EOFError, SSHException, RuntimeError, subprocess.SubprocessError):
                if output:
                    if output.channel:
                        output.channel.close()
                    output._cleanup()
                    output.log.close()
                job.finish('failed', error='admin_output_setup_failed')
                return
            run = '/bin/sh -c ' + shlex.quote(script)
            run = ('printf %s ' + shlex.quote(stdin) + ' | ' + run) if stdin is not None else run + ' </dev/null'
            out_path = shlex.quote(directory + '/stdout')
            err_path = shlex.quote(directory + '/stderr')
            out_end = shlex.quote(output.markers['stdout'].decode())
            err_end = shlex.quote(output.markers['stderr'].decode())
            payload = (f'( exec 3>{out_path} 4>{err_path}\n'
                       + run + ' >&3 2>&4 3>&- 4>&-\n__code=$?\n'
                       + f'printf %s {out_end} >&3\nprintf %s {err_end} >&4\nexit "$__code"\n)\n'
                       + '__code=$?\nprintf ' + shlex.quote(err_marker + '\\n')
                       + ' >&2\nprintf ' + shlex.quote('\\n' + marker + ':%s\\n') + ' "$__code"\n')
            try:
                self.channel.sendall(payload)
            except Exception:
                self.close()
                output.channel.close()
                job.finish('unknown', error='admin_channel_write_failed')
                return
            done = re.compile(re.escape(marker) + r':(-?\d+)\r?\n')
            decoders = {s: codecs.getincrementaldecoder('utf-8')('replace') for s in ('stdout', 'stderr')}
            buffers = {'stdout': '', 'stderr': ''}
            completed = {'stdout': False, 'stderr': False}
            code = None
            deadline = time.monotonic() + float(body['timeout']) if body.get('timeout') else None
            while self.active():
                if job.cancel_event.is_set() or (deadline is not None and time.monotonic() >= deadline):
                    self.close()
                    if code is None:
                        job.finish('unknown', error='admin_job_cancelled_or_timeout; remote process may continue')
                    else:
                        job.append('stderr', '\n[ssh-control] Output incomplete: wait cancelled or timed out.\n')
                        job.finish('completed', code)
                    return
                got = False
                for stream, available, recv in (('stdout', self.channel.recv_ready, self.channel.recv),
                                                ('stderr', self.channel.recv_stderr_ready, self.channel.recv_stderr)):
                    if not available():
                        continue
                    got = True
                    try:
                        data = recv(65535)
                    except socket.timeout:
                        continue
                    except (OSError, EOFError, SSHException):
                        for name in buffers:
                            job.append(name, buffers[name] + decoders[name].decode(b'', final=True))
                        self.close()
                        if code is None:
                            job.finish('unknown', error='admin_channel_read_failed; remote outcome unknown')
                        else:
                            job.append('stderr', '\n[ssh-control] Output incomplete: SSH channel read failed.\n')
                            job.finish('completed', code)
                        return
                    buffers[stream] += decoders[stream].decode(data)
                    if stream == 'stdout':
                        match = done.search(buffers[stream])
                        if match:
                            code = int(match.group(1))
                            output_text = buffers[stream][:match.start()]
                            job.append(stream, output_text[:-1] if output_text.endswith('\n') else output_text)
                            buffers[stream] = buffers[stream][match.end():]
                            completed[stream] = True
                    else:
                        index = buffers[stream].find(err_marker + '\n')
                        if index >= 0:
                            job.append(stream, buffers[stream][:index])
                            buffers[stream] = buffers[stream][index + len(err_marker) + 1:]
                            completed[stream] = True
                    if not completed[stream] and len(buffers[stream]) > len(marker) + 128:
                        keep = len(marker) + 128
                        job.append(stream, buffers[stream][:-keep])
                        buffers[stream] = buffers[stream][-keep:]
                if all(completed.values()) and all(e.is_set() for e in output.ready.values()):
                    job.finish('completed', code)
                    return
                if output.finished.is_set() and not all(e.is_set() for e in output.ready.values()):
                    self.close()
                    if code is None:
                        job.finish('unknown', error='admin_output_channel_closed; remote outcome unknown')
                    else:
                        job.append('stderr', '\n[ssh-control] Output incomplete: output channel closed.\n')
                        job.finish('completed', code)
                    return
                if not got:
                    time.sleep(0.01)
            for stream in buffers:
                job.append(stream, buffers[stream])
            self.close()
            if code is None:
                job.finish('unknown', error='admin_session_closed_or_expired; remote process may continue')
            else:
                job.append('stderr', '\n[ssh-control] Output incomplete: admin session closed.\n')
                job.finish('completed', code)
