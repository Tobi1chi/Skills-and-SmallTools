"""Launch the human confirmation helper in a native desktop terminal."""
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile


def launch_terminal(helper, request_id, ticket_path, port):
    launcher_path = None
    args = [sys.executable, str(helper), request_id, ticket_path, str(port)]
    if sys.platform == 'darwin':
        fd, launcher_path = tempfile.mkstemp(prefix='ssh-control-terminal-', suffix='.command')
        try:
            with os.fdopen(fd, 'w') as launcher:
                launcher.write('#!/bin/sh\nexec ' + ' '.join(map(shlex.quote, args + [launcher_path])) + '\n')
            os.chmod(launcher_path, 0o700)
            process = subprocess.Popen(['/usr/bin/open', '-a', 'Terminal', launcher_path],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        except BaseException:
            Path(launcher_path).unlink(missing_ok=True)
            raise
        return process, launcher_path
    if sys.platform == 'win32':
        if Path(args[0]).name.lower() == 'pythonw.exe':
            console_python = Path(args[0]).with_name('python.exe')
            if console_python.exists():
                args[0] = str(console_python)
        process = subprocess.Popen(args + [''], creationflags=subprocess.CREATE_NEW_CONSOLE,
                                   stdout=None, stderr=None, stdin=None)
        return process, None
    if sys.platform.startswith('linux'):
        candidates = [('x-terminal-emulator', '-e'), ('gnome-terminal', '--'), ('konsole', '-e'),
                      ('xfce4-terminal', '-x'), ('kitty', '-e'), ('alacritty', '-e'), ('xterm', '-e')]
        for name, flag in candidates:
            executable = shutil.which(name)
            if executable:
                return subprocess.Popen([executable, flag] + args + [''],
                                        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE), None
        raise RuntimeError('No supported graphical terminal found')
    raise RuntimeError('Unsupported desktop platform: ' + sys.platform)
