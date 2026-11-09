#!/bin/sh
# codex-job: detached remote jobs shared by ssh-control and plain `ssh`.
#
# ssh-control installs this file as ~/.codex-ssh-jobs/codex-job on the remote
# host. Jobs keep running when the SSH connection, the local service or the Mac
# goes away, and can be inspected/started/cancelled with plain ssh:
#
#   ssh HOST '~/.codex-ssh-jobs/codex-job list'
#   ssh HOST '~/.codex-ssh-jobs/codex-job status ID'
#   ssh HOST '~/.codex-ssh-jobs/codex-job tail ID 100'
#   ssh HOST '~/.codex-ssh-jobs/codex-job cancel ID'
#   ssh HOST '~/.codex-ssh-jobs/codex-job run "make -j8 && make test"'
#
# Layout of $CODEX_JOB_ROOT/<id>/ (default root ~/.codex-ssh-jobs):
#   run.sh stdin stdout stderr started_at pid [pgid] [exit_code] [cancelled]
# Finished job directories older than 7 days are pruned on each start.
set -u
root=${CODEX_JOB_ROOT:-"$HOME/.codex-ssh-jobs"}
action=${1:-help}
[ $# -gt 0 ] && shift

die() { printf 'codex-job: %s\n' "$1" >&2; exit "${2:-2}"; }

job_dir() {
  case ${1:-} in
    ''|*[!0-9a-f]*) die "invalid job id" ;;
  esac
  d="$root/$1"
}

alive() {
  pid=$(cat "$d/pid" 2>/dev/null) || return 1
  kill -0 "$pid" 2>/dev/null || return 1
  args=$(ps -o args= -p "$pid" 2>/dev/null) || return 0
  case $args in
    ''|*codex-job*) return 0 ;;
    *) return 1 ;;
  esac
}

state() {
  if [ -f "$d/exit_code" ]; then echo "done"
  elif alive; then echo "running"
  elif [ -f "$d/exit_code" ]; then echo "done"
  elif [ -f "$d/cancelled" ]; then echo "cancelled"
  else echo "vanished"
  fi
}

children() {
  if command -v pgrep >/dev/null 2>&1; then pgrep -P "$1" 2>/dev/null
  else ps -A -o pid= -o ppid= 2>/dev/null | awk -v p="$1" '$2 == p { print $1 }'
  fi
}

kill_tree() {
  # Stop first so nothing new is spawned, then terminate children before parents.
  kill -STOP "$1" 2>/dev/null
  for c in $(children "$1"); do kill_tree "$c"; done
  kill -TERM "$1" 2>/dev/null
  kill -CONT "$1" 2>/dev/null
}

new_id() {
  od -An -N16 -tx1 /dev/urandom 2>/dev/null | tr -d ' \n'
}

start() {
  # start ID SCRIPT   (job stdin = this process's stdin)
  job_dir "${1:-}"
  script=${2:-}
  [ -n "$script" ] || die "empty script"
  umask 077
  mkdir -p "$root" && mkdir "$d" || die "cannot create $d" 90
  printf '%s\n' "$script" > "$d/run.sh"
  cat > "$d/stdin"
  : > "$d/stdout"
  : > "$d/stderr"
  date -u +%Y-%m-%dT%H:%M:%SZ > "$d/started_at"
  cd "$HOME" 2>/dev/null || cd /
  # `trap '' HUP` instead of nohup: macOS nohup refuses to run without a console
  # ("can't detach from console"). The runner records its own pid (and pgid when
  # setsid made it a session leader) so a forking setsid cannot mislead us.
  runner='trap "" HUP; d=$1; echo $$ >"$d/pid"; [ "${2:-}" = setsid ] && echo $$ >"$d/pgid"; /bin/sh "$d/run.sh" <"$d/stdin" >>"$d/stdout" 2>>"$d/stderr"; s=$?; echo "$s" >"$d/exit_code.tmp" && mv "$d/exit_code.tmp" "$d/exit_code"'
  if command -v setsid >/dev/null 2>&1; then
    setsid /bin/sh -c "$runner" codex-job "$d" setsid </dev/null >/dev/null 2>&1 &
  else
    /bin/sh -c "$runner" codex-job "$d" </dev/null >/dev/null 2>&1 &
  fi
  [ -s "$d/pid" ] || echo $! > "$d/pid"
  find "$root" -mindepth 2 -maxdepth 2 -name exit_code -mtime +7 2>/dev/null |
    while IFS= read -r f; do rm -rf -- "${f%/exit_code}"; done
  printf 'started %s %s\n' "$1" "$(cat "$d/pid")"
}

case $action in
  start)
    start "$@"
    ;;
  run)
    [ $# -gt 0 ] || die "usage: codex-job run 'COMMAND'"
    id=$(new_id)
    [ -n "$id" ] || die "cannot generate id"
    start "$id" "$*" </dev/null
    ;;
  poll)
    # poll ID STDOUT_OFFSET STDERR_OFFSET [MAX_BYTES]: new bytes on stdout/stderr.
    # exit 0 running, 10 done, 11 finished during poll, 12 vanished, 13 cancelled, 3 missing
    job_dir "${1:-}"
    [ -d "$d" ] || exit 3
    max=${4:-1048576}
    done_before=0
    [ -f "$d/exit_code" ] && done_before=1
    tail -c "+$((${2:-0} + 1))" "$d/stdout" 2>/dev/null | head -c "$max"
    tail -c "+$((${3:-0} + 1))" "$d/stderr" 2>/dev/null | head -c "$max" >&2
    [ "$done_before" = 1 ] && exit 10
    alive && exit 0
    [ -f "$d/exit_code" ] && exit 11
    [ -f "$d/cancelled" ] && exit 13
    exit 12
    ;;
  size)
    job_dir "${1:-}"
    [ -d "$d" ] || exit 3
    printf '%s %s\n' "$(wc -c < "$d/stdout" | tr -d ' ')" "$(wc -c < "$d/stderr" | tr -d ' ')"
    ;;
  exit-code)
    job_dir "${1:-}"
    cat "$d/exit_code" 2>/dev/null || exit 3
    ;;
  status)
    job_dir "${1:-}"
    [ -d "$d" ] || die "no such job" 3
    printf 'id=%s state=%s exit_code=%s started_at=%s pid=%s\n' "$1" "$(state)" \
      "$(cat "$d/exit_code" 2>/dev/null)" "$(cat "$d/started_at" 2>/dev/null)" "$(cat "$d/pid" 2>/dev/null)"
    ;;
  list)
    [ -d "$root" ] || exit 0
    for x in "$root"/*/; do
      [ -f "${x}run.sh" ] || continue
      id=$(basename "$x"); d="$root/$id"
      printf '%s %s %s %s\n' "$id" "$(state)" "$(cat "$d/started_at" 2>/dev/null)" \
        "$(head -c 80 "$d/run.sh" | tr '\n' ' ')"
    done
    ;;
  tail)
    job_dir "${1:-}"
    [ -d "$d" ] || die "no such job" 3
    tail -n "${2:-50}" "$d/stdout"
    tail -n "${2:-50}" "$d/stderr" >&2
    ;;
  cancel)
    job_dir "${1:-}"
    [ -d "$d" ] || die "no such job" 3
    [ -f "$d/exit_code" ] && { echo "already finished"; exit 0; }
    : > "$d/cancelled"
    if [ -f "$d/pgid" ]; then
      # No `--`: dash's kill builtin rejects it ("Illegal number").
      kill -TERM "-$(cat "$d/pgid")" 2>/dev/null || kill_tree "$(cat "$d/pid")"
    else
      pid=$(cat "$d/pid" 2>/dev/null) && kill_tree "$pid"
    fi
    echo "cancel requested"
    ;;
  *)
    sed -n '2,16p' "$0" 2>/dev/null || echo "usage: codex-job start|run|poll|size|exit-code|status|list|tail|cancel"
    ;;
esac
