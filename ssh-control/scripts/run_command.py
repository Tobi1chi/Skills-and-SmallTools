# Run with: uv run --with paramiko python scripts/run_command.py
r"""
SSH 远程命令执行脚本（短连接，每条命令独立 channel）
用法：
  uv run --with paramiko python scripts/run_command.py --alias ALIAS --cmd "COMMAND"
  uv run --with paramiko python scripts/run_command.py --host HOST --cmd "CMD1" --cmd "CMD2"

目标：
  --alias  connections.json 别名或 ~/.ssh/config 的 Host
  --host   主机名；与 `ssh HOST` 一样套用 ~/.ssh/config
  --port/--user/--key/--passphrase 覆盖解析结果

可选参数：
  --timeout SECONDS     连接超时秒数（默认 10）
  --sudo                以 sudo -n 执行命令（需要密码时请用持久服务的 --sudo-password-env）

输出：JSON 数组，每条命令对应一个结果对象
"""

import argparse
import json
import shlex

from ssh_connect import add_target_args, connect_from_args


def main():
    parser = argparse.ArgumentParser()
    add_target_args(parser)
    parser.add_argument("--cmd", action="append", required=True, dest="commands")
    parser.add_argument("--timeout", type=int, default=10)
    parser.add_argument("--sudo", action="store_true")
    args = parser.parse_args()

    client, proxy = connect_from_args(args, timeout=args.timeout)
    results = []
    try:
        for cmd in args.commands:
            full_cmd = f"sudo -n -- /bin/sh -c {shlex.quote(cmd)}" if args.sudo else cmd
            try:
                stdin, stdout, stderr = client.exec_command(full_cmd, timeout=60)
                stdin.close()
                out = stdout.read().decode("utf-8", errors="replace")
                err = stderr.read().decode("utf-8", errors="replace")
                results.append({"command": cmd, "stdout": out, "stderr": err,
                                "exit_code": stdout.channel.recv_exit_status()})
            except Exception as e:
                results.append({"command": cmd, "error": str(e), "exit_code": -1})
    finally:
        client.close()
        if proxy is not None:
            proxy.close()
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
