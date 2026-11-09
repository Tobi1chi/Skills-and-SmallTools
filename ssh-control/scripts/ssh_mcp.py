"""MCP (streamable HTTP, JSON responses) front end for the ssh-control service.

Served at POST /mcp by ssh_server.py, behind the same token/Host/Origin checks.
Tools call the in-process SessionRegistry directly, so MCP and ssh_client.py
share sessions, detached jobs, safety checks and host-key verification.
Results are compact text (output, then one status line) to keep context small.
"""
import os

from ssh_connect import ConnectError, public_connection
from ssh_execution import native_hint
import ssh_sftp

SERVER_INFO = {"name": "ssh-control", "version": "2.1.0"}
PROTOCOL_VERSIONS = ("2026-07-28", "2025-06-18", "2025-03-26", "2024-11-05")
DEFAULT_MAX_OUTPUT = 20000
MAX_EXEC_TIMEOUT = 600

INSTRUCTIONS = (
    "SSH to hosts by alias (every Host in ~/.ssh/config plus the skill's connections.json). "
    "ssh_exec keeps one persistent shell per alias (cd/export persist); use mode=exec for an "
    "isolated /bin/sh with cwd/env/stdin. Use ssh_job for anything that may exceed ~30s: it runs "
    "detached on the remote host and survives disconnects. Dangerous commands are rejected; "
    "ask the user before destructive operations. Never print secrets."
)

_EXEC_PROPS = {
    "cwd": {"type": "string", "description": "Working directory (mode=exec / jobs only)."},
    "env": {"type": "object", "additionalProperties": {"type": "string"},
            "description": "Extra environment variables (mode=exec / jobs only). Never secrets."},
    "stdin": {"type": "string", "description": "Data fed to stdin (mode=exec / jobs only)."},
    "sudo": {"type": "boolean", "description": "Run via passwordless `sudo -n`. Password sudo is CLI-only."},
}

TOOLS = [
    {
        "name": "ssh_hosts",
        "description": "List SSH aliases this service can reach and the currently open sessions.",
        "inputSchema": {"type": "object", "properties": {
            "reload": {"type": "boolean", "description": "Re-read ~/.ssh/config and connections.json first."},
        }},
        "annotations": {"readOnlyHint": True, "openWorldHint": False},
    },
    {
        "name": "ssh_exec",
        "description": ("Run a command on a host and wait for it. mode=shell (default) uses the alias's "
                        "persistent shell, so cd/export carry over between calls; stdin is /dev/null. "
                        "The status line ends with the shell's cwd after the command. "
                        "mode=exec runs in a fresh /bin/sh channel and accepts cwd/env/stdin. Output keeps "
                        "the newest max_output characters per stream. Use ssh_job for long commands."),
        "inputSchema": {"type": "object", "required": ["alias", "cmd"], "properties": {
            "alias": {"type": "string"},
            "cmd": {"type": "string"},
            "mode": {"type": "string", "enum": ["shell", "exec"], "default": "shell"},
            "timeout": {"type": "number", "default": 30, "maximum": MAX_EXEC_TIMEOUT,
                        "description": "Seconds. A shell-mode timeout closes that shell (outcome uncertain)."},
            "max_output": {"type": "integer", "default": DEFAULT_MAX_OUTPUT},
            **_EXEC_PROPS,
        }},
        "annotations": {"openWorldHint": True},
    },
    {
        "name": "ssh_job",
        "description": ("Long-running commands. start: runs detached under ~/.codex-ssh-jobs on the host "
                        "(survives SSH drops and service restarts) and returns job_id. wait: blocks up to "
                        "timeout (max 50s) and returns output after `cursor` plus the next cursor. status: "
                        "state plus output tail. cancel, list. attach: follow a job id started with native "
                        "ssh (`codex-job run`). Never replay a job whose state is unknown; inspect first."),
        "inputSchema": {"type": "object", "required": ["action"], "properties": {
            "action": {"type": "string", "enum": ["start", "wait", "status", "cancel", "list", "attach"]},
            "alias": {"type": "string", "description": "start / attach"},
            "cmd": {"type": "string", "description": "start"},
            "job_id": {"type": "string", "description": "wait / status / cancel / attach"},
            "cursor": {"type": "integer", "default": 0, "description": "wait: cursor from the previous result"},
            "timeout": {"type": "number", "default": 30, "description": "wait: seconds, max 50"},
            "attached": {"type": "boolean", "description": "start: stream over one channel instead (ends with it)"},
            "max_output": {"type": "integer", "default": DEFAULT_MAX_OUTPUT},
            **_EXEC_PROPS,
        }},
        "annotations": {"openWorldHint": True},
    },
    {
        "name": "ssh_transfer",
        "description": "SFTP over the alias's existing SSH connection. local must be an absolute path on this Mac.",
        "inputSchema": {"type": "object", "required": ["alias", "direction", "local", "remote"], "properties": {
            "alias": {"type": "string"},
            "direction": {"type": "string", "enum": ["upload", "download"]},
            "local": {"type": "string"},
            "remote": {"type": "string"},
            "recursive": {"type": "boolean", "default": False},
        }},
        "annotations": {"openWorldHint": True},
    },
    {
        "name": "ssh_session_reset",
        "description": ("Close the alias's sessions so the next call opens a fresh SSH connection and shell "
                        "(e.g. after group membership changes). Detached jobs keep running."),
        "inputSchema": {"type": "object", "required": ["alias"], "properties": {"alias": {"type": "string"}}},
        "annotations": {"openWorldHint": False, "idempotentHint": True},
    },
]


class ToolError(Exception):
    pass


def rpc_error(msg_id, code, message):
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


def _clip(text, limit):
    if len(text) <= limit:
        return text
    return f"[... {len(text) - limit} earlier chars omitted]\n" + text[-limit:]


def _render(result, limit, extra=""):
    parts = []
    out, err = result.get("stdout") or "", result.get("stderr") or ""
    if out:
        parts.append(_clip(out, limit).rstrip("\n"))
    if err:
        parts.append("[stderr]\n" + _clip(err, limit).rstrip("\n"))
    state = result.get("state")
    status = [] if state == "running" else [f"exit {result.get('exit_code')}"]
    if state and state != "completed":
        status.insert(0, state)
    if result.get("duration_ms") is not None:
        status.append(f"{result['duration_ms']} ms")
    if result.get("cwd"):
        status.append(f"cwd {result['cwd']}")
    for key in ("error", "shell_restarted"):
        if result.get(key):
            status.append(f"{key}: {result[key]}")
    if result.get("output_truncated"):
        status.append("output_truncated (service kept newest 1 MiB)")
    if extra:
        status.append(extra)
    parts.append("[" + " · ".join(status) + "]")
    return "\n".join(parts)


def _int(args, key, default, low=None, high=None):
    try:
        value = type(default)(args.get(key, default))
    except (TypeError, ValueError):
        raise ToolError(f"{key} must be a number")
    if low is not None:
        value = max(low, value)
    if high is not None:
        value = min(high, value)
    return value


def _exec_body(args):
    body = {"cmd": args["cmd"]}
    for key in ("cwd", "env", "stdin", "sudo"):
        if args.get(key) not in (None, "", {}):
            body[key] = args[key]
    return body


class MCPServer:
    def __init__(self, registry):
        self.registry = registry

    # ------------------------------------------------------------ JSON-RPC

    def handle(self, message):
        if isinstance(message, list):   # 2025-03-26 batches
            replies = [r for r in (self.handle_one(m) for m in message) if r is not None]
            return replies or None
        return self.handle_one(message)

    def handle_one(self, message):
        if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
            return rpc_error(None, -32600, "invalid request")
        method = message.get("method")
        msg_id = message.get("id")
        if method is None or "id" not in message:   # response or notification
            return None
        params = message.get("params") or {}
        if method == "initialize":
            requested = params.get("protocolVersion")
            version = requested if requested in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[1]
            return {"jsonrpc": "2.0", "id": msg_id, "result": {
                "protocolVersion": version,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": SERVER_INFO,
                "instructions": INSTRUCTIONS,
            }}
        if method == "ping":
            return {"jsonrpc": "2.0", "id": msg_id, "result": {}}
        if method == "tools/list":
            return {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": TOOLS}}
        if method == "tools/call":
            name = params.get("name")
            args = params.get("arguments") or {}
            handler = getattr(self, "tool_" + str(name), None)
            if handler is None or not isinstance(args, dict):
                return rpc_error(msg_id, -32602, f"unknown tool: {name}")
            text, is_error = self.call(handler, args)
            return {"jsonrpc": "2.0", "id": msg_id, "result": {
                "content": [{"type": "text", "text": text}], "isError": is_error}}
        return rpc_error(msg_id, -32601, f"method not found: {method}")

    def call(self, handler, args):
        try:
            return handler(args), False
        except ToolError as exc:
            return str(exc), True
        except ConnectError as exc:
            hint = (" Do not edit known_hosts; tell the user (the real host may simply be off)."
                    if exc.code == "host_key_mismatch" else "")
            return f"{exc.code}: {exc.message}{hint}", True
        except KeyError as exc:
            return f"unknown connection alias or missing argument: {exc}. Try ssh_hosts.", True
        except PermissionError as exc:
            return (f"dangerous command rejected ({exc}). Needs explicit user approval; "
                    "do not rephrase it to slip past the check."), True
        except (ValueError, TypeError) as exc:
            return f"invalid request: {str(exc)[:300]}", True
        except (ConnectionError, TimeoutError, RuntimeError, OSError) as exc:
            return f"remote_operation_failed: {str(exc)[:300]}", True

    # ------------------------------------------------------------ tools

    def _session(self, alias):
        if not alias:
            raise ToolError("alias is required")
        return self.registry.get_or_create(str(alias))[0]

    def tool_ssh_hosts(self, args):
        reg = self.registry
        lines = []
        if args.get("reload"):
            change = reg.reload()
            summary = "; ".join(f"{k} {', '.join(v)}" for k, v in change.items() if v)
            lines.append("reload: " + (summary or "no changes"))
        with reg.lock:
            items = sorted(reg.connections.values(), key=lambda c: c["alias"])
        for c in map(public_connection, items):
            via = " via proxy" if c["uses_proxy"] else ""
            lines.append(f"{c['alias']}: {c['username']}@{c['host']}:{c['port']} ({c['source']}{via})")
        sessions = reg.list_sessions()
        if sessions:
            lines.append("open sessions: " + ", ".join(
                f"{s['alias']}{'' if s['shell_alive'] else ' (shell closed)'}" for s in sessions))
        return "\n".join(lines) or "no aliases configured"

    def tool_ssh_exec(self, args):
        if not args.get("cmd"):
            raise ToolError("cmd is required")
        limit = _int(args, "max_output", DEFAULT_MAX_OUTPUT, 200)
        timeout = _int(args, "timeout", 30.0, 1.0, float(MAX_EXEC_TIMEOUT))
        mode = args.get("mode") or "shell"
        if mode not in ("shell", "exec"):
            raise ToolError("mode must be shell or exec")
        session = self._session(args.get("alias"))
        body = _exec_body(args)
        if mode == "exec" or body.get("sudo"):
            body["timeout"] = timeout
            job = self.registry.start_job(session, body)
            with job.condition:
                job.condition.wait_for(lambda: job.state != "running", timeout=timeout + 1)
            result = job.snapshot(0)
            extra = ""
            if result["state"] == "running":
                extra = f"still running as job {job.job_id}; use ssh_job wait, do not replay"
            return _render(result, limit, extra)
        if any(k in body for k in ("cwd", "env", "stdin")):
            raise ToolError("cwd/env/stdin need mode=exec; in shell mode use cd/export")
        reason = self.registry.check_command(body["cmd"])
        if reason:
            raise PermissionError(reason)
        return _render(session.execute(body["cmd"], timeout=timeout), limit)

    def tool_ssh_job(self, args):
        reg = self.registry
        action = args.get("action")
        limit = _int(args, "max_output", DEFAULT_MAX_OUTPUT, 200)
        if action == "list":
            with reg.lock:
                jobs = [j.summary() for j in reg.jobs.values()]
            if not jobs:
                return "no tracked jobs"
            return "\n".join(f"{j['job_id']}  {j['state']:<9} exit={j['exit_code']}  {j['alias'] or '-'}"
                             for j in sorted(jobs, key=lambda j: j["started_at"]))
        if action == "start":
            if not args.get("cmd"):
                raise ToolError("cmd is required")
            session = self._session(args.get("alias"))
            detached = not args.get("attached") and not session.is_powershell
            job = reg.start_job(session, _exec_body(args), detached=detached)
            hint = native_hint(session.alias, job.job_id) if detached else None
            text = f"started job {job.job_id} ({'detached' if detached else 'attached'}); next: ssh_job wait cursor=0"
            return text + (f"\nnative: {hint}" if hint else "")
        job_id = str(args.get("job_id") or "")
        if not job_id:
            raise ToolError("job_id is required")
        if action == "attach":
            job = reg.attach_job(str(args.get("alias") or ""), job_id)
            reg.ensure_attached(job)
            return _render(job.snapshot(), limit, f"cursor {job.cursor}")
        job = reg.get_job(job_id)
        if job is None:
            raise ToolError("job not found; for a detached job started elsewhere use action=attach with alias")
        if action == "cancel":
            result = reg.cancel_job(job)
            return f"cancel {job_id}: " + ", ".join(f"{k}={v}" for k, v in result.items() if k != "job_id")
        reg.ensure_attached(job)
        if action == "status":
            snap = job.snapshot()
        elif action == "wait":
            snap = job.wait(_int(args, "cursor", 0, 0), _int(args, "timeout", 30.0, 0.0, 50.0))
        else:
            raise ToolError("action must be start, wait, status, cancel, list or attach")
        extra = [f"cursor {snap['cursor']}"]
        if snap.get("phase"):
            extra.append(f"phase {snap['phase']}")
        if snap.get("truncated"):
            extra.append("older output dropped")
        if snap.get("detached") and not snap.get("attached") and snap["state"] == "running":
            extra.append("detached, not attached right now (output resumes on next call)")
        return _render(snap, limit, " · ".join(extra))

    def tool_ssh_transfer(self, args):
        direction, local, remote = args.get("direction"), args.get("local"), args.get("remote")
        if direction not in ("upload", "download") or not local or not remote:
            raise ToolError("direction (upload|download), local and remote are required")
        if not os.path.isabs(os.path.expanduser(local)):
            raise ToolError("local path must be absolute")
        session = self._session(args.get("alias"))
        sftp = session.client.open_sftp()
        try:
            fn = ssh_sftp.upload if direction == "upload" else ssh_sftp.download
            src, dst = (local, remote) if direction == "upload" else (remote, local)
            result = fn(sftp, src, dst, bool(args.get("recursive")))
        finally:
            sftp.close()
        text = f"{direction}: {result['total']} file(s), {result['failed']} failed"
        if result.get("errors"):
            text += "\n" + "\n".join(map(str, result["errors"][:20]))
        return text

    def tool_ssh_session_reset(self, args):
        alias = str(args.get("alias") or "")
        with self.registry.lock:
            ids = [s.session_id for s in self.registry.sessions.values() if s.alias == alias]
        for session_id in ids:
            self.registry.delete(session_id)
        return f"closed {len(ids)} session(s) for {alias}"
