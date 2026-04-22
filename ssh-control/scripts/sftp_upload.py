# Run with: uv run --with paramiko python scripts/sftp_upload.py
r"""
SFTP 文件上传脚本
用法：
  uv run --with paramiko python scripts/sftp_upload.py --host HOST --user USER --key KEY_PATH \
      --local /path/to/local/file --remote /path/on/server/file

  # 上传整个目录（递归）
  uv run --with paramiko python scripts/sftp_upload.py --host HOST --user USER --key KEY_PATH \
      --local ./myapp/ --remote /var/www/myapp/ --recursive
"""

import argparse
import sys
import json
import os
import paramiko
from pathlib import Path


def load_private_key(key_path, passphrase=None):
    for key_class in [paramiko.RSAKey, paramiko.Ed25519Key, paramiko.ECDSAKey]:
        try:
            return key_class.from_private_key_file(str(key_path), password=passphrase)
        except Exception:
            continue
    raise ValueError(f"无法识别私钥格式或密码错误：{key_path}")


def upload(host, username, key_path, local_path, remote_path, port=22,
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

    def ensure_remote_dir(sftp, remote_dir):
        dirs = []
        path = remote_dir
        while path not in ("", "/"):
            dirs.append(path)
            path = os.path.dirname(path)
        for d in reversed(dirs):
            try:
                sftp.mkdir(d)
            except IOError:
                pass  # 目录已存在

    def upload_file(local_file, remote_file):
        try:
            ensure_remote_dir(sftp, os.path.dirname(remote_file))
            sftp.put(str(local_file), remote_file)
            transferred.append({"local": str(local_file), "remote": remote_file})
        except Exception as e:
            errors.append({"local": str(local_file), "remote": remote_file, "error": str(e)})

    if local_path.is_dir() and recursive:
        for root, dirs, files in os.walk(local_path):
            rel_root = Path(root).relative_to(local_path)
            for f in files:
                local_file = Path(root) / f
                remote_file = os.path.join(remote_path, str(rel_root), f).replace("\\", "/")
                upload_file(local_file, remote_file)
    elif local_path.is_file():
        upload_file(local_path, remote_path)
    else:
        print(json.dumps({"error": f"本地路径不存在或是目录（需加 --recursive）：{local_path}"}))
        sftp.close()
        client.close()
        sys.exit(1)

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
    parser.add_argument("--local", required=True)
    parser.add_argument("--remote", required=True)
    parser.add_argument("--passphrase", default=None)
    parser.add_argument("--recursive", action="store_true")
    args = parser.parse_args()

    upload(
        host=args.host, username=args.user, key_path=args.key,
        local_path=args.local, remote_path=args.remote,
        port=args.port, passphrase=args.passphrase, recursive=args.recursive,
    )


if __name__ == "__main__":
    main()
