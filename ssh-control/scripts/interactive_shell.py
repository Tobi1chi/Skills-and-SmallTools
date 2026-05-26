# Run with: uv run --with paramiko python scripts/interactive_shell.py
r"""
SSH 交互式 Shell 脚本 —— 在同一个远端 shell 会话中执行多步骤命令
用法：
  uv run --with paramiko python scripts/interactive_shell.py --host HOST --user USER --key KEY_PATH \
      --steps '["cd /var/www", "pwd", "export FOO=bar", "echo $FOO"]'

参数：
  --steps JSON_ARRAY    要按顺序执行的命令列表（JSON 字符串）
  --env KEY=VAL         设置环境变量（可多次使用）
  --shell SHELL         使用的远端 shell（默认 /bin/bash，适合 Linux 服务器）
  --timeout SECONDS     每条命令超时（默认 30）

说明：
  此脚本使用同一个交互式 shell channel，命令间状态会保留，因此 cd、
  export、变量赋值等会影响后续步骤。命令结束通过唯一 sentinel 判断，
  不依赖远端 shell prompt 的文本形态。
"""

import argparse
import json
import re
import shlex
import sys
import time
import uuid
from pathlib import Path

import paramiko


ENV_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
BRACKETED_PASTE_RE = re.compile(r"\x1b\[\?2004[hl]")


def load_private_key(key_path, passphrase=None):
    for key_class in [paramiko.RSAKey, paramiko.Ed25519Key, paramiko.ECDSAKey]:
        try:
            return key_class.from_private_key_file(str(key_path), password=passphrase)
        except Exception:
            continue
    raise ValueError(f"无法识别私钥格式或密码错误：{key_path}")


def validate_steps(steps):
    if not isinstance(steps, list) or not steps:
        raise ValueError("--steps 必须是非空 JSON 数组")
    for index, step in enumerate(steps, start=1):
        if not isinstance(step, str) or not step.strip():
            raise ValueError(f"--steps 第 {index} 项必须是非空字符串")


def parse_env_vars(env_vars):
    exports = []
    for kv in env_vars or []:
        if "=" not in kv:
            raise ValueError(f"--env 必须使用 KEY=VAL 格式：{kv}")
        name, value = kv.split("=", 1)
        if not ENV_NAME_RE.match(name):
            raise ValueError(f"--env 变量名非法：{name}")
        exports.append((name, value))
    return exports


def shell_start_command(shell):
    quoted_shell = shlex.quote(shell)
    if Path(shell).name in ("bash", "sh"):
        if Path(shell).name == "bash":
            return f"exec {quoted_shell} --noprofile --norc"
        return f"exec {quoted_shell}"
    return f"exec {quoted_shell}"


def drain_channel(channel, quiet_seconds=0.4, max_seconds=3):
    output = b""
    deadline = time.time() + max_seconds
    quiet_deadline = time.time() + quiet_seconds
    while time.time() < deadline:
        if channel.recv_ready():
            chunk = channel.recv(4096)
            if not chunk:
                break
            output += chunk
            quiet_deadline = time.time() + quiet_seconds
        elif time.time() >= quiet_deadline:
            break
        else:
            time.sleep(0.05)
    return output.decode("utf-8", errors="replace")


def read_until(channel, marker, timeout):
    output = b""
    marker_pattern = re.compile(re.escape(marker).encode("utf-8") + rb":-?\d+\r?\n")
    deadline = time.time() + timeout
    while time.time() < deadline:
        if channel.recv_ready():
            chunk = channel.recv(4096)
            if not chunk:
                break
            output += chunk
            if marker_pattern.search(output):
                return output.decode("utf-8", errors="replace"), False
        else:
            time.sleep(0.05)
    return output.decode("utf-8", errors="replace"), True


def strip_wrapped_output(raw_output, start_marker, done_marker):
    raw_output = BRACKETED_PASTE_RE.sub("", raw_output)
    raw_output = raw_output.replace("\r\n", "\n")
    start_index = raw_output.rfind(start_marker)
    if start_index == -1:
        body = raw_output
    else:
        body = raw_output[start_index + len(start_marker):]
        if body.startswith("\n"):
            body = body[1:]

    done_index = body.find(done_marker)
    if done_index != -1:
        body = body[:done_index]
        if body.endswith("\n"):
            body = body[:-1]

    return body


def parse_exit_code(raw_output, done_marker):
    pattern = re.compile(re.escape(done_marker) + r":(-?\d+)")
    match = pattern.search(raw_output)
    if not match:
        return None
    return int(match.group(1))


def interactive_session(host, username, key_path, steps, port=22, passphrase=None,
                        env_vars=None, shell="/bin/bash", cmd_timeout=30):
    validate_steps(steps)
    exports = parse_env_vars(env_vars)

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    key_path = Path(key_path).expanduser()
    try:
        pkey = load_private_key(key_path, passphrase)
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False))
        sys.exit(1)

    channel = None
    try:
        client.connect(host, port=port, username=username, pkey=pkey, timeout=10)
        channel = client.invoke_shell(term="xterm", width=220, height=50)
        channel.settimeout(cmd_timeout)

        drain_channel(channel)
        channel.send(shell_start_command(shell) + "\n")
        drain_channel(channel)
        channel.send(
            "unset PROMPT_COMMAND\n"
            "export PS1='' PS2='' PS0=''\n"
            "bind 'set enable-bracketed-paste off' 2>/dev/null || true\n"
            "stty -echo -onlcr 2>/dev/null || true\n"
        )
        drain_channel(channel)

        for name, value in exports:
            channel.send(f"export {name}={shlex.quote(value)}\n")
            drain_channel(channel, quiet_seconds=0.2, max_seconds=1)

        results = []
        for cmd in steps:
            command_id = uuid.uuid4().hex
            start_marker = f"__CODX_START_{command_id}__"
            done_marker = f"__CODX_DONE_{command_id}__"
            wrapped = (
                f"printf '\\n{start_marker}\\n'\n"
                "set +e\n"
                f"{cmd}\n"
                "__codex_status=$?\n"
                "set +e\n"
                f"printf '\\n{done_marker}:%s\\n' \"$__codex_status\"\n"
            )
            channel.send(wrapped)
            raw_output, timed_out = read_until(channel, done_marker, cmd_timeout)
            exit_code = parse_exit_code(raw_output, done_marker)
            stdout = strip_wrapped_output(raw_output, start_marker, done_marker)

            result = {
                "command": cmd,
                "stdout": stdout,
                "stderr": "",
                "exit_code": exit_code if exit_code is not None else -1,
            }
            if timed_out:
                result["error"] = f"命令超时（{cmd_timeout} 秒）"
            elif exit_code is None:
                result["error"] = "未检测到命令结束 sentinel"
            results.append(result)
            if timed_out or exit_code is None:
                break

        print(json.dumps(results, ensure_ascii=False, indent=2))
    except Exception as e:
        print(json.dumps({"error": f"交互式会话失败：{e}"}, ensure_ascii=False))
        sys.exit(1)
    finally:
        if channel is not None:
            channel.close()
        client.close()


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
        validate_steps(steps)
        parse_env_vars(args.env_vars)
    except (json.JSONDecodeError, ValueError) as e:
        print(json.dumps({"error": f"参数错误：{e}"}, ensure_ascii=False))
        sys.exit(1)

    interactive_session(
        host=args.host, username=args.user, key_path=args.key,
        steps=steps, port=args.port, passphrase=args.passphrase,
        env_vars=args.env_vars, shell=args.shell, cmd_timeout=args.timeout,
    )


if __name__ == "__main__":
    main()
