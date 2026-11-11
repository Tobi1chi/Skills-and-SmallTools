"""Per-command admin output streams and bounded local task logs."""
import codecs
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import socket
import subprocess
import threading
import time

from paramiko import SSHException
from ssh_execution import remote_exec

_log_lock = threading.Lock()
_active_logs = set()


class AdminLog:
    def __init__(self, directory, keep, job_id):
        self.directory = Path(directory)
        self.keep = keep
        self.path = self.directory / f'ssh-admin-{time.time_ns()}-{job_id}.jsonl'
        self.lock = threading.Lock()
        with _log_lock:
            self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            self.file = os.fdopen(fd, 'w', encoding='utf-8')
            _active_logs.add(str(self.path))
            try:
                self._prune()
            except (OSError, subprocess.SubprocessError, RuntimeError):
                self.file.close()
                _active_logs.discard(str(self.path))
                raise

    def _prune(self):
        files = sorted((p for p in self.directory.glob('ssh-admin-*.jsonl')
                        if re.fullmatch(r'ssh-admin-\d+-[0-9a-f]{32}\.jsonl', p.name)),
                       key=lambda p: p.name, reverse=True)
        old = [p for p in files[self.keep:] if str(p) not in _active_logs]
        if old:
            trash = shutil.which('trash') or shutil.which('trash-put')
            if not trash:
                raise RuntimeError('trash command required to prune admin logs')
            subprocess.run([trash, *map(str, old)], check=True, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)

    def write(self, stream, data):
        if data:
            self.record({'stream': stream, 'data': data})

    def record(self, value):
        with self.lock:
            self.file.write(json.dumps(value, ensure_ascii=False) + '\n')
            self.file.flush()

    def close(self):
        with self.lock:
            if not self.file.closed:
                self.file.close()
        with _log_lock:
            _active_logs.discard(str(self.path))
            self._prune()


class AdminOutput:
    def __init__(self, session, job, log_dir, log_keep):
        self.session, self.job = session, job
        self.log = AdminLog(log_dir, log_keep, job.job_id)
        self.job.log_path = str(self.log.path)
        self.ready = {'stdout': threading.Event(), 'stderr': threading.Event()}
        self.finished = threading.Event()
        self.failure = None
        self.log_error = False
        self.directory = None
        self.channel = None
        self.markers = {s: ('__CODEX_STREAM_' + job.job_id + '_' + s + '__').encode()
                        for s in ('stdout', 'stderr')}
        self.buffers = {s: b'' for s in self.markers}
        self.decoders = {s: codecs.getincrementaldecoder('utf-8')('replace') for s in self.markers}

    def start(self):
        prepare = ('umask 077; d=$(mktemp -d "${TMPDIR:-/tmp}/ssh-control-stream.XXXXXXXX") || exit; '
                   'mkfifo "$d/stdout" "$d/stderr" || exit; printf %s "$d"')
        code, out, _ = remote_exec(self.session, prepare, timeout=15)
        if code != 0:
            raise RuntimeError('admin_stream_setup_failed')
        self.directory = out.decode('utf-8')
        self.channel = self.session.client.get_transport().open_session(timeout=10)
        self.channel.settimeout(0.2)
        out_path, err_path = (shlex.quote(self.directory + '/' + s) for s in ('stdout', 'stderr'))
        command = f'cat {out_path} & cat {err_path} >&2 & wait'
        self.channel.exec_command('/bin/sh -c ' + shlex.quote(command))
        threading.Thread(target=self._pump, daemon=True).start()
        return self.directory

    def _append(self, stream, data, final=False):
        text = self.decoders[stream].decode(data, final=final)
        if text:
            if not self.log_error:
                try:
                    self.log.write(stream, text)
                except OSError:
                    self.log_error = True
                    self.job.append('stderr', '[ssh-control] Local task log write failed.\n')
            self.job.append(stream, text)

    def _consume(self, stream, data):
        if self.ready[stream].is_set():
            self._append(stream, data)
            return
        buf = self.buffers[stream] + data
        marker = self.markers[stream]
        at = buf.find(marker)
        if at >= 0:
            self._append(stream, buf[:at])
            self.ready[stream].set()
            self._append(stream, buf[at + len(marker):])
            self.buffers[stream] = b''
        elif len(buf) >= len(marker):
            cut = len(buf) - len(marker) + 1
            self._append(stream, buf[:cut])
            self.buffers[stream] = buf[cut:]
        else:
            self.buffers[stream] = buf

    def _cleanup(self):
        if not self.directory:
            return
        try:
            sftp = self.session.client.open_sftp()
            try:
                for name in ('stdout', 'stderr'):
                    sftp.remove(self.directory + '/' + name)
                sftp.rmdir(self.directory)
            finally:
                sftp.close()
        except (OSError, EOFError, SSHException):
            pass  # A disconnected remote may retain only the empty FIFO endpoints.

    def _pump(self):
        try:
            while True:
                got = False
                for stream, available, recv in (('stdout', self.channel.recv_ready, self.channel.recv),
                                                ('stderr', self.channel.recv_stderr_ready, self.channel.recv_stderr)):
                    if available():
                        try:
                            data = recv(65535)
                        except socket.timeout:
                            continue
                        if data:
                            got = True
                            self._consume(stream, data)
                if self.channel.exit_status_ready() and not self.channel.recv_ready() and not self.channel.recv_stderr_ready():
                    if self.channel.recv_exit_status() != 0:
                        self.failure = 'admin_stream_reader_failed'
                    break
                if self.channel.closed or not self.session.transport_active():
                    self.failure = 'admin_stream_disconnected'
                    break
                if not got:
                    time.sleep(0.01)
        except (OSError, EOFError, SSHException):
            self.failure = 'admin_stream_read_failed'
        finally:
            for stream in self.buffers:
                self._append(stream, self.buffers[stream], final=True)
            self.finished.set()
            self.channel.close()
            self._cleanup()
            try:
                self.log.close()
            except (OSError, subprocess.SubprocessError, RuntimeError):
                self.job.append('stderr', '[ssh-control] Local task log retention failed.\n')
