# Run with: uv run --with paramiko python scripts/sftp_download.py
r"""
SFTP 文件下载脚本
用法：
  uv run --with paramiko python scripts/sftp_download.py --host HOST --user USER --key KEY_PATH \
      --remote /path/on/server/file.log --local /local/save/path/

  # 下载整个目录（递归）
  uv run --with paramiko python scripts/sftp_download.py --host HOST --user USER --key KEY_PATH \
      --remote /var/www/myapp/ --local ./backup/ --recursive
"""

import argparse
import sys
import json
import os
import stat
import paramiko
from pathlib import Path


def load_private_key(key_path, passphrase=None):
    for key_class in [paramiko.RSAKey, paramiko.Ed25519Key, paramiko.ECDSAKey]:
        try:
            return key_class.from_private_key_file(str(key_path), password=passphrase)
        except Exception:
            continue
    raise ValueError(f"无法识别私钥格式或密码错误：{key_path}")


def download(host, username, key_path, remote_path, local_path, port=22,
             passphrase=None, recursive=False):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    key_path = Path(key_path).expanduser()
    local_path = Path(local_path).expanduser()

    try:
        pkey = load_private_key(key_path, passphrase)
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)

    try:
        client.connect(host, port=port, username=username, pkey=pkey, timeout=10)
    except Exception as e:
        print(json.dumps({"error": f"连接失败：{e}"}))
        sys.exit(1)

    sftp = client.open_sftp()
    transferred = []
    errors = []

    def is_dir(path):
        try:
            return stat.S_ISDIR(sftp.stat(path).st_mode)
        except Exception:
            return False

    def download_file(remote_file, local_file):
        try:
            local_file.parent.mkdir(parents=True, exist_ok=True)
            sftp.get(remote_file, str(local_file))
            transferred.append({"remote": remote_file, "local": str(local_file)})
        except Exception as e:
            errors.append({"remote": remote_file, "local": str(local_file), "error": str(e)})

    def download_dir(remote_dir, local_dir):
        local_dir.mkdir(parents=True, exist_ok=True)
        for entry in sftp.listdir_attr(remote_dir):
            r = remote_dir.rstrip("/") + "/" + entry.filename
            l = local_dir / entry.filename
            if stat.S_ISDIR(entry.st_mode):
                download_dir(r, l)
            else:
                download_file(r, l)

    if is_dir(remote_path):
        if recursive:
            download_dir(remote_path, local_path)
        else:
            print(json.dumps({"error": f"远端路径是目录，需加 --recursive：{remote_path}"}))
            sftp.close()
            client.close()
            sys.exit(1)
    else:
        dest = local_path if not local_path.is_dir() else local_path / Path(remote_path).name
        download_file(remote_path, dest)

    sftp.close()
    client.close()
    print(json.dumps({
        "transferred": transferred,
        "errors": errors,
        "total": len(transferred),
        "failed": len(errors)
    }, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=22)
    parser.add_argument("--user", required=True)
    parser.add_argument("--key", required=True)
    parser.add_argument("--remote", required=True)
    parser.add_argument("--local", required=True)
    parser.add_argument("--passphrase", default=None)
    parser.add_argument("--recursive", action="store_true")
    args = parser.parse_args()

    download(
        host=args.host, username=args.user, key_path=args.key,
        remote_path=args.remote, local_path=args.local,
        port=args.port, passphrase=args.passphrase, recursive=args.recursive,
    )


if __name__ == "__main__":
    main()
