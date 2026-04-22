# Run with: uv run --with paramiko python scripts/interactive_shell.py
r"""
SSH 交互式 Shell 脚本 —— 模拟人类操作 Shell 的多步骤会话
用法：
  uv run --with paramiko python scripts/interactive_shell.py --host HOST --user USER --key KEY_PATH \
      --steps '["cd /var/www", "ls -la", "cat app.log | tail -20"]'

参数：
  --steps JSON_ARRAY    要按顺序执行的命令列表（JSON 字符串）
  --env KEY=VAL         设置环境变量（可多次使用）
  --shell SHELL         使用的远端 shell（默认 /bin/bash，适合 Linux 服务器）
  --timeout SECONDS     每条命令超时（默认 30）

说明：
  与 run_command.py 不同，此脚本在同一个 shell 会话中执行所有命令，
  因此 `cd`、`export`、变量赋值等状态会在命令间保留。
  适合需要「先 cd 再操作」「先设置环境变量再运行程序」等场景。
"""

import argparse
import sys
import json
import time
import paramiko
from pathlib import Path


def load_private_key(key_path, passphrase=None):
    for key_class in [paramiko.RSAKey, paramiko.Ed25519Key, paramiko.ECDSAKey]:
        try:
            return key_class.from_private_key_file(str(key_path), password=passphrase)
        except Exception:
            continue
    raise ValueError(f"无法识别私钥格式或密码错误：{key_path}")


def interactive_session(host, username, key_path, steps, port=22, passphrase=None,
                         env_vars=None, shell="/bin/bash", cmd_timeout=30):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    key_path = Path(key_path).expanduser()
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

    # 开启一个持久 shell channel
    channel = client.invoke_shell(term="xterm", width=220, height=50)
    channel.settimeout(cmd_timeout)

    def read_until_prompt(timeout=5):
        """读取输出直到出现 shell 提示符或超时"""
        output = b""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if channel.recv_ready():
                chunk = channel.recv(4096)
                if not chunk:
                    break
                output += chunk
                # 简单的提示符检测（$ 或 # 结尾）
                decoded = output.decode("utf-8", errors="replace")
                if decoded.rstrip().endswith(("$ ", "# ", "% ")):
                    break
            else:
                time.sleep(0.1)
        return output.decode("utf-8", errors="replace")

    # 设置环境变量
    if env_vars:
        for kv in env_vars:
            channel.send(f"export {kv}\n")
            time.sleep(0.2)

    # 丢弃初始欢迎信息
    read_until_prompt(timeout=3)

    results = []
    for cmd in steps:
        channel.send(cmd + "\n")
        time.sleep(0.3)
        raw_output = read_until_prompt(timeout=cmd_timeout)
        # 去掉首行（命令回显）和末行（下一个提示符）
        lines = raw_output.splitlines()
        if lines and cmd.strip() in lines[0]:
            lines = lines[1:]
        if lines and lines[-1].rstrip().endswith(("$ ", "# ", "% ")):
            lines = lines[:-1]
        output = "\n".join(lines)
        results.append({"command": cmd, "output": output})

    channel.close()
    client.close()
    print(json.dumps(results, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=22)
    parser.add_argument("--user", required=True)
    parser.add_argument("--key", required=True)
    parser.add_argument("--steps", required=True, help='JSON 数组，如 ["cd /app", "ls"]')
    parser.add_argument("--env", action="append", dest="env_vars", default=[])
    parser.add_argument("--shell", default="/bin/bash")
    parser.add_argument("--passphrase", default=None)
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()

    try:
        steps = json.loads(args.steps)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"--steps 不是合法的 JSON 数组：{e}"}))
        sys.exit(1)

    interactive_session(
        host=args.host, username=args.user, key_path=args.key,
        steps=steps, port=args.port, passphrase=args.passphrase,
        env_vars=args.env_vars, shell=args.shell, cmd_timeout=args.timeout,
    )


if __name__ == "__main__":
    main()
