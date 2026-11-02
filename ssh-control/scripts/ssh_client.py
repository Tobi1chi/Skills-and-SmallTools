"""Unified HTTP client; never restarts the shared service or replays commands."""
import argparse
import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def request(base, method, path, body=None, timeout=60):
    data = json.dumps(body).encode() if body is not None else None
    req = Request(base.rstrip('/') + path, data=data, method=method,
                  headers={"Content-Type": "application/json"})
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:8765')
    sub = parser.add_subparsers(dest='action', required=True)
    sub.add_parser('health')
    sub.add_parser('connections')
    sub.add_parser('reload')
    run = sub.add_parser('exec')
    jobs = sub.add_parser('jobs').add_subparsers(dest='job_action', required=True)
    start = jobs.add_parser('start')
    for p in (run, start):
        target = p.add_mutually_exclusive_group(required=True)
        target.add_argument('--alias')
        target.add_argument('--session')
        p.add_argument('--force-new', action='store_true')
        p.add_argument('--shell', default='/bin/bash')
        p.add_argument('--cmd', required=True)
        p.add_argument('--mode', choices=['shell', 'exec'], default='shell' if p is run else 'exec')
        p.add_argument('--sudo', action='store_true')
        p.add_argument('--sudo-password-env')
        p.add_argument('--cwd')
        p.add_argument('--env', action='append', default=[], metavar='NAME=VALUE')
        p.add_argument('--stdin', action='store_true', help='Read business input from local stdin')
        p.add_argument('--timeout', type=float, default=None)
    status = jobs.add_parser('status')
    status.add_argument('job_id')
    wait = jobs.add_parser('wait')
    wait.add_argument('job_id')
    wait.add_argument('--cursor', type=int, default=0)
    wait.add_argument('--phase-version', type=int)
    wait.add_argument('--timeout', type=float, default=30)
    args = parser.parse_args()
    if args.action in ('health', 'connections'):
        result = request(args.url, 'GET', '/' + args.action)
    elif args.action == 'reload':
        result = request(args.url, 'POST', '/connections/reload', {})
    elif args.action == 'jobs' and args.job_action in ('status', 'wait'):
        path = '/jobs/' + args.job_id
        result = request(args.url, 'GET', path) if args.job_action == 'status' else request(
            args.url, 'POST', path + '/wait', dict(cursor=args.cursor, timeout=args.timeout,
                                                 phase_version=args.phase_version))
    else:
        if args.force_new and args.session:
            parser.error('--force-new requires --alias')
        if args.sudo_password_env and not args.sudo:
            parser.error('--sudo-password-env requires --sudo')
        # Check presence locally; LaunchAgent environment is irrelevant.
        password = os.environ.get(args.sudo_password_env) if args.sudo_password_env else None
        if args.sudo_password_env and password is None:
            parser.error('specified sudo password environment variable is unset')
        health = request(args.url, 'GET', '/health')
        if health.get('status') != 'ok':
            result = health
        else:
            session_id = args.session
            if not session_id:
                session = request(args.url, 'POST', '/sessions', dict(alias=args.alias,
                                  shell=args.shell, force_new=args.force_new))
                session_id = session.get('session_id')
                if not session_id:
                    print(json.dumps(session, ensure_ascii=False))
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
            result = request(args.url, 'POST', '/sessions/' + session_id + '/' + endpoint,
                             body, timeout=(args.timeout or 30) + 10 if endpoint == 'exec' else 60)
            body.pop('sudo_password', None)
            password = None
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get('error') or result.get('exit_code') not in (None, 0):
        sys.exit(1)


if __name__ == '__main__':
    main()
