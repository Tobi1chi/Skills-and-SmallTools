"""Unified HTTP client; never restarts the shared service or replays commands."""
import argparse
import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ssh_token import ensure_token

DEFAULT_URL = os.environ.get("SSH_CONTROL_URL", "http://127.0.0.1:47622")


def load_token():
    """Token from SSH_CONTROL_TOKEN or the skill's .env (created on first use); never printed."""
    token = os.environ.get("SSH_CONTROL_TOKEN")
    if token:
        return token.strip()
    return ensure_token()


def request(base, method, path, body=None, timeout=60):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    token = load_token()
    if token:
        headers["Authorization"] = "Bearer " + token
    req = Request(base.rstrip('/') + path, data=data, method=method, headers=headers)
    try:
        with urlopen(req, timeout=timeout) as response:
            return json.load(response)
    except HTTPError as exc:
        try:
            return json.load(exc)
        except Exception:
            return {"error": "http_error", "http_status": exc.code}
    except (URLError, TimeoutError, OSError):
        return {"error": "service_unavailable_or_wait_timeout", "detail": "No restart or replay; check health/job status."}


def add_target(p):
    target = p.add_mutually_exclusive_group(required=True)
    target.add_argument('--alias', help='connections.json alias or ~/.ssh/config Host')
    target.add_argument('--session')
    p.add_argument('--force-new', action='store_true')
    p.add_argument('--shell', default='/bin/bash')


def open_session(args):
    """Return (session_id, None) or (None, error_result)."""
    health = request(args.url, 'GET', '/health')
    if health.get('status') != 'ok':
        return None, health
    if args.session:
        return args.session, None
    session = request(args.url, 'POST', '/sessions', dict(alias=args.alias, shell=args.shell,
                                                          force_new=args.force_new))
    if not session.get('session_id'):
        return None, session
    return session['session_id'], None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default=DEFAULT_URL, help='service URL (env SSH_CONTROL_URL)')
    sub = parser.add_subparsers(dest='action', required=True)
    sub.add_parser('health')
    sub.add_parser('connections')
    sub.add_parser('reload')
    admin = sub.add_parser('admin')
    admin.add_argument('admin_action', choices=['request', 'status', 'close'])
    admin.add_argument('--alias', required=True)
    admin.add_argument('--log-dir', help='absolute directory in the local workspace; required for request')
    admin.add_argument('--log-keep', type=int, default=50, help='number of recent admin task logs to retain')
    approval = sub.add_parser('approval').add_subparsers(dest='approval_action', required=True)
    approval_request = approval.add_parser('request')
    approval_request.add_argument('--alias', required=True)
    approval_request.add_argument('--cmd', required=True)
    approval_request.add_argument('--explanation', required=True)
    approval_request.add_argument('--sudo', action='store_true')
    approval_request.add_argument('--cwd')
    approval_status = approval.add_parser('status')
    approval_status.add_argument('request_id')
    login = sub.add_parser('login').add_subparsers(dest='login_action', required=True)
    login_request = login.add_parser('request')
    login_request.add_argument('--alias', required=True)
    login_request.add_argument('--env-var')
    login_status = login.add_parser('status')
    login_status.add_argument('request_id')
    run = sub.add_parser('exec')
    jobs = sub.add_parser('jobs').add_subparsers(dest='job_action', required=True)
    start = jobs.add_parser('start')
    for p in (run, start):
        add_target(p)
        p.add_argument('--cmd', required=True)
        p.add_argument('--mode', choices=['shell', 'exec'], default='shell' if p is run else 'exec')
        p.add_argument('--sudo', action='store_true')
        p.add_argument('--sudo-password-env')
        p.add_argument('--cwd')
        p.add_argument('--env', action='append', default=[], metavar='NAME=VALUE')
        p.add_argument('--stdin', action='store_true', help='Read business input from local stdin')
        p.add_argument('--timeout', type=float, default=None)
    start.add_argument('--attached', action='store_true',
                       help='stream over one SSH channel instead of a detached remote job')
    status = jobs.add_parser('status')
    status.add_argument('job_id')
    wait = jobs.add_parser('wait')
    wait.add_argument('job_id')
    wait.add_argument('--cursor', type=int, default=0)
    wait.add_argument('--phase-version', type=int)
    wait.add_argument('--timeout', type=float, default=30)
    cancel = jobs.add_parser('cancel')
    cancel.add_argument('job_id')
    attach = jobs.add_parser('attach', help='follow a detached job id (e.g. started with native codex-job run)')
    attach.add_argument('--alias', required=True)
    attach.add_argument('job_id')
    jobs.add_parser('list')
    for name in ('upload', 'download'):
        p = sub.add_parser(name)
        add_target(p)
        p.add_argument('--local', required=True)
        p.add_argument('--remote', required=True)
        p.add_argument('--recursive', action='store_true')
    args = parser.parse_args()

    if args.action in ('health', 'connections'):
        result = request(args.url, 'GET', '/' + args.action)
    elif args.action == 'reload':
        result = request(args.url, 'POST', '/connections/reload', {})
    elif args.action == 'admin':
        result = request(args.url, 'POST', '/admins', dict(action=args.admin_action, alias=args.alias,
                                                          log_dir=args.log_dir, log_keep=args.log_keep))
    elif args.action == 'approval':
        if args.approval_action == 'request':
            result = request(args.url, 'POST', '/approvals', dict(alias=args.alias, cmd=args.cmd,
                             explanation=args.explanation, sudo=args.sudo, cwd=args.cwd))
        else:
            result = request(args.url, 'GET', '/approvals/' + args.request_id)
    elif args.action == 'login':
        if args.login_action == 'request':
            result = request(args.url, 'POST', '/logins', dict(alias=args.alias, env_var=args.env_var))
        else:
            result = request(args.url, 'GET', '/approvals/' + args.request_id)
    elif args.action == 'jobs' and args.job_action == 'list':
        result = request(args.url, 'GET', '/jobs')
    elif args.action == 'jobs' and args.job_action == 'attach':
        result = request(args.url, 'POST', '/jobs/attach', dict(alias=args.alias, job_id=args.job_id))
    elif args.action == 'jobs' and args.job_action in ('status', 'wait', 'cancel'):
        path = '/jobs/' + args.job_id
        if args.job_action == 'status':
            result = request(args.url, 'GET', path)
        elif args.job_action == 'cancel':
            result = request(args.url, 'POST', path + '/cancel', {})
        else:
            result = request(args.url, 'POST', path + '/wait', dict(
                cursor=args.cursor, timeout=args.timeout, phase_version=args.phase_version),
                timeout=args.timeout + 30)
    elif args.action in ('upload', 'download'):
        session_id, error = open_session(args)
        if error is not None:
            result = error
        else:
            result = request(args.url, 'POST', '/sessions/' + session_id + '/sftp', dict(
                direction=args.action, local=os.path.abspath(os.path.expanduser(args.local)),
                remote=args.remote, recursive=args.recursive), timeout=3600)
    else:
        if args.force_new and args.session:
            parser.error('--force-new requires --alias')
        if args.sudo_password_env and not args.sudo:
            parser.error('--sudo-password-env requires --sudo')
        # Check presence locally; LaunchAgent environment is irrelevant.
        password = os.environ.get(args.sudo_password_env) if args.sudo_password_env else None
        if args.sudo_password_env and password is None:
            parser.error('specified sudo password environment variable is unset')
        session_id, error = open_session(args)
        if error is not None:
            print(json.dumps(error, ensure_ascii=False))
            sys.exit(1)
        body = dict(cmd=args.cmd, mode=args.mode, sudo=args.sudo)
        if args.timeout is not None:
            body['timeout'] = args.timeout
        if args.cwd:
            body['cwd'] = args.cwd
        if args.env:
            try:
                body['env'] = dict(value.split('=', 1) for value in args.env)
            except ValueError:
                parser.error('--env requires NAME=VALUE')
        if args.stdin:
            body['stdin'] = sys.stdin.read()
        if password is not None:
            body['sudo_password'] = password
        endpoint = 'jobs' if args.action == 'jobs' else 'exec'
        if endpoint == 'jobs' and args.attached:
            body['attached'] = True
        result = request(args.url, 'POST', '/sessions/' + session_id + '/' + endpoint,
                         body, timeout=(args.timeout or 30) + 10 if endpoint == 'exec' else 60)
        body.pop('sudo_password', None)
        password = None
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get('error') or result.get('exit_code') not in (None, 0):
        sys.exit(1)


if __name__ == '__main__':
    main()
