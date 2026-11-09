# Run with: uv run --with paramiko python scripts/sftp_download.py
r"""
SFTP 文件下载脚本（短连接）。持久服务可用时优先 `ssh_client.py download`，
目录同步优先原生 `rsync -a ALIAS:REMOTE LOCAL`（同样读取 ~/.ssh/config）。
用法：
  uv run --with paramiko python scripts/sftp_download.py --alias ALIAS \
      --remote /path/on/server/file.log --local /local/save/path/
  # 下载整个目录（递归）
  uv run --with paramiko python scripts/sftp_download.py --host HOST \
      --remote /var/www/myapp/ --local ./backup/ --recursive
"""

import argparse
import json
import sys

import ssh_sftp
from ssh_connect import add_target_args, connect_from_args


def main():
    parser = argparse.ArgumentParser()
    add_target_args(parser)
    parser.add_argument("--local", required=True)
    parser.add_argument("--remote", required=True)
    parser.add_argument("--recursive", action="store_true")
    args = parser.parse_args()

    client, proxy = connect_from_args(args)
    try:
        sftp = client.open_sftp()
        try:
            result = ssh_sftp.download(sftp, args.remote, args.local, args.recursive)
        finally:
            sftp.close()
    except ValueError as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False))
        sys.exit(1)
    finally:
        client.close()
        if proxy is not None:
            proxy.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["failed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
