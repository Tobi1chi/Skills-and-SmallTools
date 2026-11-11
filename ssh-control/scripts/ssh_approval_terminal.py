"""Human confirmation window for one immutable ssh-control command."""
import getpass
import os
import re
import subprocess
import sys
from pathlib import Path

from ssh_client import request


def display(value):
    """Keep untrusted terminal control characters from altering the prompt."""
    return "".join(c if c in "\n\t" or (ord(c) >= 32 and not 127 <= ord(c) <= 159)
                   else f"\\x{ord(c):02x}" for c in str(value))


def variable_value(name):
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        raise ValueError("环境变量名无效")
    if os.environ.get(name):
        return os.environ[name]
    if sys.platform == 'win32':
        import winreg
        locations = ((winreg.HKEY_CURRENT_USER, r'Environment'),
                     (winreg.HKEY_LOCAL_MACHINE, r'SYSTEM\CurrentControlSet\Control\Session Manager\Environment'))
        for root, key_path in locations:
            try:
                with winreg.OpenKey(root, key_path) as key:
                    value, _ = winreg.QueryValueEx(key, name)
                    return os.path.expandvars(str(value))
            except FileNotFoundError:
                continue
        return ''
    # GUI-launched processes may not inherit interactive shell exports.
    shell = Path(os.environ.get('SHELL', '/bin/zsh' if sys.platform == 'darwin' else '/bin/bash'))
    rc = '.zshrc' if shell.name == 'zsh' else '.bashrc' if shell.name == 'bash' else None
    if not rc:
        return ''
    program = 'source "$HOME/' + rc + '" >/dev/null 2>&1; printenv "$1"'
    result = subprocess.run([str(shell), '-c', program, 'ssh-control', name],
                            capture_output=True, text=True, timeout=15)
    if result.returncode != 0:
        return ''
    return result.stdout[:-1] if result.stdout.endswith('\n') else result.stdout


def login(url, base, ticket, details):
    print("\n=== SSH 密码连接 ===")
    print(f"主机: {display(details['alias'])} ({display(details['user'])}@{display(details['host'])}:{details['port']})")
    try:
        name = details.get("env_var")
        if not name:
            name = input("环境变量名（直接回车手动输入密码，输入 N 取消）: ").strip()
        if name.lower() == "n":
            password = None
        elif name:
            password = variable_value(name)
            if not password:
                print("环境变量为空或未设置，请手动输入密码。")
                password = getpass.getpass("SSH 密码: ")
        else:
            password = getpass.getpass("SSH 密码: ")
        if not password:
            password = None
    except (EOFError, KeyboardInterrupt, ValueError, subprocess.SubprocessError) as exc:
        print("已取消或无法读取环境变量。")
        password = None
    body = {"ticket": ticket, "password": password}
    result = request(url, "POST", base + "/login", body, timeout=60)
    body.pop("password", None)
    password = None
    if result.get("error"):
        print("连接失败:", display(result.get("error")), display(result.get("detail") or ""))
        return 1
    print("连接状态:", display(result["state"]))
    return 0 if result["state"] == "connected" else 1


def admin_login(url, base, ticket, details):
    print('\n=== SSH 临时管理员会话 ===')
    print(f"主机: {display(details['alias'])} ({display(details['user'])}@{display(details['host'])}:{details['port']})")
    print('授权后该 SSH 会话可使用 root 权限 15 分钟；高风险命令仍需单独确认。')
    print(f"本地任务日志: {display(details['log_dir'])}（保留最近 {details['log_keep']} 条）")
    try:
        answer = input('确认开启？输入 Y 确认，输入 N 或直接回车取消 [y/N]: ').strip().lower()
        password = getpass.getpass('远端 sudo 密码（免密 sudo 直接回车）: ') if answer == 'y' else None
    except (EOFError, KeyboardInterrupt):
        password = None
    body = {'ticket': ticket, 'password': password}
    result = request(url, 'POST', base + '/admin', body, timeout=60)
    body.pop('password', None)
    password = None
    if result.get('error'):
        print('提权失败:', display(result.get('error')), display(result.get('detail') or ''))
        return 1
    print('管理员会话状态:', display(result['state']))
    return 0 if result['state'] == 'active' else 1


def main():
    request_id, ticket_path, port, launcher_path = sys.argv[1:]
    if launcher_path:
        Path(launcher_path).unlink(missing_ok=True)
    path = Path(ticket_path)
    ticket = path.read_text()
    path.unlink()
    url = f"http://127.0.0.1:{int(port)}"
    base = f"/approvals/{request_id}"
    details = request(url, "POST", base + "/details", {"ticket": ticket})
    if details.get("error") or details.get("state") != "pending":
        print("审批请求不可用或已过期。")
        return 1
    if details.get("kind") == "login":
        return login(url, base, ticket, details)
    if details.get("kind") == "admin":
        return admin_login(url, base, ticket, details)
    print("\n=== SSH 高风险操作审批 ===")
    print(f"主机: {display(details['alias'])} ({display(details['user'])}@{display(details['host'])}:{details['port']})")
    print(f"执行身份: {'sudo/root' if details['sudo'] else display(details['user'])}")
    if details.get('use_admin'):
        print('将使用当前临时管理员会话；到期后需要重新提权。')
    print(f"工作目录: {display(details['cwd'] or '远端登录默认目录')}")
    print(f"说明:\n{display(details['explanation'])}")
    print(f"命令:\n{display(details['cmd'])}")
    try:
        answer = input("\n确认执行？输入 Y 执行，输入 N 或直接回车拒绝 [y/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        answer = "n"
    decision = "approve" if answer == "y" else "reject"
    body = {"ticket": ticket, "decision": decision}
    if decision == "approve" and details["sudo"] and not details.get("use_admin"):
        try:
            password = getpass.getpass("远端 sudo 密码（免密 sudo 直接回车）: ")
        except (EOFError, KeyboardInterrupt):
            body["decision"] = "reject"
        else:
            if password:
                body["password"] = password
            password = None
    result = request(url, "POST", base + "/decision", body)
    body.pop("password", None)
    if result.get("error"):
        print("审批未执行:", display(result.get("detail") or result["error"]))
        return 1
    if result["state"] != "started":
        print("状态:", display(result["state"]))
        return 0
    job_id = result["job_id"]
    print(f"已提交任务 {job_id}，等待结果……")
    cursor = 0
    while True:
        result = request(url, "POST", f"/jobs/{job_id}/wait", {"cursor": cursor, "timeout": 30}, timeout=40)
        if not result.get("state"):
            print("无法确认任务状态，请检查任务 ID；不要重复执行。")
            return 1
        print(display(result.get("stdout") or ""), end="", flush=True)
        print(display(result.get("stderr") or ""), end="", file=sys.stderr, flush=True)
        cursor = result.get("cursor", cursor)
        if result["state"] != "running":
            print(f"\n状态: {result['state']}，退出码: {result.get('exit_code')}，原因: {result.get('error') or '无'}")
            return 0 if result.get("exit_code") == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
