# Run with: uv run --with paramiko python scripts/sftp_upload.py
r"""
SFTP 文件上传脚本（短连接）。持久服务可用时优先 `ssh_client.py upload`，
目录同步优先原生 `rsync -a LOCAL ALIAS:REMOTE`（同样读取 ~/.ssh/config）。
用法：
  uv run --with paramiko python scripts/sftp_upload.py --alias ALIAS \
      --local /path/to/local/file --remote /path/on/server/file
  # 上传整个目录（递归）
  uv run --with paramiko python scripts/sftp_upload.py --host HOST \
      --local ./myapp/ --remote /var/www/myapp/ --recursive
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
            result = ssh_sftp.upload(sftp, args.local, args.remote, args.recursive)
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
