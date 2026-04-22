# Run with: uv run --with paramiko python scripts/run_command.py
r"""
SSH 远程命令执行脚本
用法：
  uv run --with paramiko python scripts/run_command.py --host HOST --user USER --key KEY_PATH --cmd "COMMAND"
  uv run --with paramiko python scripts/run_command.py --host HOST --user USER --key KEY_PATH --cmd "CMD1" --cmd "CMD2"

可选参数：
  --port PORT           SSH 端口（默认 22）
  --passphrase PASS     私钥密码（如有）
  --timeout SECONDS     连接超时秒数（默认 10）
  --sudo                以 sudo 执行命令

输出：JSON 数组，每条命令对应一个结果对象
"""

import argparse
import sys
import json
import paramiko
from pathlib import Path


def load_private_key(key_path, passphrase=None):
    """尝试加载各种格式的私钥（RSA / Ed25519 / ECDSA）"""
    for key_class in [paramiko.RSAKey, paramiko.Ed25519Key, paramiko.ECDSAKey]:
        try:
            return key_class.from_private_key_file(str(key_path), password=passphrase)
        except Exception:
            continue
    raise ValueError(f"无法识别私钥格式或密码错误：{key_path}")


def run_commands(host, username, key_path, commands, port=22, passphrase=None, timeout=10, use_sudo=False):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    key_path = Path(key_path).expanduser()
    try:
        pkey = load_private_key(key_path, passphrase)
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)

    try:
        client.connect(host, port=port, username=username, pkey=pkey, timeout=timeout)
    except Exception as e:
        print(json.dumps({"error": f"连接失败：{e}"}))
        sys.exit(1)

    results = []
    for cmd in commands:
        full_cmd = f"sudo {cmd}" if use_sudo else cmd
        try:
            _, stdout, stderr = client.exec_command(full_cmd, timeout=60)
            out = stdout.read().decode("utf-8", errors="replace")
            err = stderr.read().decode("utf-8", errors="replace")
            exit_code = stdout.channel.recv_exit_status()
            results.append({
                "command": full_cmd,
                "stdout": out,
                "stderr": err,
                "exit_code": exit_code
            })
        except Exception as e:
            results.append({"command": full_cmd, "error": str(e), "exit_code": -1})

    client.close()
    print(json.dumps(results, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=22)
    parser.add_argument("--user", required=True)
    parser.add_argument("--key", required=True)
    parser.add_argument("--cmd", action="append", required=True, dest="commands")
    parser.add_argument("--passphrase", default=None)
    parser.add_argument("--timeout", type=int, default=10)
    parser.add_argument("--sudo", action="store_true")
    args = parser.parse_args()

    run_commands(
        host=args.host, username=args.user, key_path=args.key,
        commands=args.commands, port=args.port, passphrase=args.passphrase,
        timeout=args.timeout, use_sudo=args.sudo,
    )


if __name__ == "__main__":
    main()
