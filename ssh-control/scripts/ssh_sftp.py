"""SFTP transfer helpers shared by the service and the short-lived scripts."""
import os
import stat
from pathlib import Path

LIST_LIMIT = 50


def _result(transferred, errors):
    return {
        "total": len(transferred),
        "failed": len(errors),
        "transferred": transferred[:LIST_LIMIT],
        "transferred_truncated": len(transferred) > LIST_LIMIT,
        "errors": errors[:LIST_LIMIT],
    }


def _ensure_remote_dir(sftp, remote_dir):
    dirs = []
    path = remote_dir
    while path not in ("", "/", "."):
        dirs.append(path)
        path = os.path.dirname(path)
    for d in reversed(dirs):
        try:
            sftp.stat(d)
        except IOError:
            sftp.mkdir(d)


def upload(sftp, local_path, remote_path, recursive=False):
    local_path = Path(local_path).expanduser()
    transferred, errors = [], []

    def put(local_file, remote_file):
        try:
            _ensure_remote_dir(sftp, os.path.dirname(remote_file))
            sftp.put(str(local_file), remote_file)
            transferred.append({"local": str(local_file), "remote": remote_file})
        except Exception as exc:
            errors.append({"local": str(local_file), "remote": remote_file, "error": str(exc)})

    if local_path.is_dir():
        if not recursive:
            raise ValueError(f"local path is a directory; use recursive: {local_path}")
        for root, _dirs, files in os.walk(local_path):
            rel_root = Path(root).relative_to(local_path)
            for name in files:
                remote_file = "/".join(p for p in (remote_path.rstrip("/"), str(rel_root), name) if p and p != ".")
                put(Path(root) / name, remote_file)
    elif local_path.is_file():
        try:
            if stat.S_ISDIR(sftp.stat(remote_path).st_mode):
                remote_path = remote_path.rstrip("/") + "/" + local_path.name
        except IOError:
            pass
        put(local_path, remote_path)
    else:
        raise ValueError(f"local path does not exist: {local_path}")
    return _result(transferred, errors)


def download(sftp, remote_path, local_path, recursive=False):
    local_path = Path(local_path).expanduser()
    transferred, errors = [], []

    def get(remote_file, local_file):
        try:
            local_file.parent.mkdir(parents=True, exist_ok=True)
            sftp.get(remote_file, str(local_file))
            transferred.append({"remote": remote_file, "local": str(local_file)})
        except Exception as exc:
            errors.append({"remote": remote_file, "local": str(local_file), "error": str(exc)})

    def get_dir(remote_dir, local_dir):
        local_dir.mkdir(parents=True, exist_ok=True)
        for entry in sftp.listdir_attr(remote_dir):
            r = remote_dir.rstrip("/") + "/" + entry.filename
            l = local_dir / entry.filename
            if stat.S_ISDIR(entry.st_mode):
                get_dir(r, l)
            else:
                get(r, l)

    try:
        is_dir = stat.S_ISDIR(sftp.stat(remote_path).st_mode)
    except IOError:
        raise ValueError(f"remote path does not exist: {remote_path}")
    if is_dir:
        if not recursive:
            raise ValueError(f"remote path is a directory; use recursive: {remote_path}")
        get_dir(remote_path, local_path)
    else:
        dest = local_path / Path(remote_path).name if local_path.is_dir() else local_path
        get(remote_path, dest)
    return _result(transferred, errors)
