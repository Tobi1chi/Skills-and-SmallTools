"""Best-effort detection of obviously destructive shell commands.

This is a seatbelt, not an authorization boundary: shell code can always hide
intent (variables, eval, base64, scripts on disk). The goal is to catch the
common literal forms while not blocking read-only inspection such as
`cat /etc/passwd`, `grep DROP app.log` or `fdisk -l`.
"""
import re
import shlex

# Words that may precede the real command in a segment.
_PREFIXES = {"sudo", "doas", "exec", "nohup", "time", "nice", "ionice", "env", "command",
             "builtin", "xargs", "stdbuf", "timeout", "busybox"}
_ARG_FLAGS = {
    "sudo": {"-u", "-g", "-C", "-D", "-h", "-p", "-r", "-t", "-U", "-T"},
    "doas": {"-u", "-C"},
    "nice": {"-n"},
    "ionice": {"-c", "-n", "-p"},
    "timeout": {"-s", "-k", "--signal", "--kill-after"},
    "env": {"-u", "-C", "-S"},
    "stdbuf": {"-i", "-o", "-e"},
    "xargs": {"-I", "-n", "-P", "-L", "-d", "-E", "-s", "-a"},
}
_SEGMENT_SPLIT =re.compile(r"\|\||&&|[;&|\n]|\$\(|`|\(|\)|\{|\}")
_ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")

_CRITICAL_DIRS = {"/", "/*", "~", "~/", "~/*", "$HOME", "${HOME}", "$HOME/", "$HOME/*", "/root",
                  "/home", "/etc", "/usr", "/var", "/boot", "/bin", "/sbin", "/lib", "/lib64",
                  "/opt", "/srv", "/dev", "/proc", "/sys", "/System", "/Users", "/Applications",
                  "/Library", "/private", "/mnt", "/media", "C:\\", "C:/"}
_ACCOUNT_FILES = r"/etc/(?:sudoers(?:\.d(?:/\S*)?)?|passwd|shadow|gshadow|group)\b"
_BLOCK_DEV = r"/dev/(?:sd[a-z]|nvme\d|vd[a-z]|hd[a-z]|xvd[a-z]|mmcblk\d|disk\d|rdisk\d|md\d|dm-\d|mapper/)"

_RAW_PATTERNS = [
    # Writes to account/sudo files: redirection, tee, in-place editors, copies.
    re.compile(r">>?\s*" + _ACCOUNT_FILES),
    re.compile(r"\btee\b(?:\s+-\S+)*\s+[^|;&]*" + _ACCOUNT_FILES),
    re.compile(r"\b(?:sed|perl)\s+(?:[^|;&]*\s)?-i\S*\s+[^|;&]*" + _ACCOUNT_FILES),
    re.compile(r"\b(?:vi|vim|nvim|nano|emacs|ed|cp|mv|install|ln|truncate|chmod|chown|rm|dd)\b"
               r"[^|;&\n]*\s" + _ACCOUNT_FILES),
    # Raw writes to block devices.
    re.compile(r">\s*" + _BLOCK_DEV),
    re.compile(r"\bdd\b[^|;&\n]*\bof=" + _BLOCK_DEV),
    # Fork bomb.
    re.compile(r":\s*\(\s*\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:"),
]

# Destructive SQL only counts when a database client is in the same command.
_SQL_DESTRUCTIVE = re.compile(r"\b(?:DROP\s+(?:TABLE|DATABASE|SCHEMA)|TRUNCATE(?:\s+TABLE)?)\b", re.I)
_DB_CLIENT = re.compile(r"\b(?:psql|mysql|mariadb|sqlite3|sqlcmd|clickhouse-client|cqlsh|mongosh?)\b")


def _segments(command):
    for part in _SEGMENT_SPLIT.split(command):
        part = part.strip()
        if not part:
            continue
        try:
            words = shlex.split(part, comments=True)
        except ValueError:
            words = part.split()
        # Drop wrappers (with their flags/arguments) and VAR=value assignments.
        while words:
            word = words[0]
            if _ASSIGN.match(word):
                words = words[1:]
                continue
            if word.rsplit("/", 1)[-1] not in _PREFIXES:
                break
            prefix = word.rsplit("/", 1)[-1]
            words = words[1:]
            while words and words[0].startswith("-"):
                flag = words.pop(0)
                if flag in _ARG_FLAGS.get(prefix, ()) and words:
                    words.pop(0)
            if prefix in ("timeout", "busybox") and words and prefix == "timeout":
                words = words[1:]  # duration
        if words:
            yield words


def _short_flags(args):
    flags = set()
    for arg in args:
        if arg.startswith("--"):
            flags.add(arg)
        elif arg.startswith("-") and len(arg) > 1:
            flags.update("-" + c for c in arg[1:])
    return flags


def _targets(args):
    return [a for a in args if not a.startswith("-")]


def _is_critical(path):
    p = path.rstrip("/") or "/"
    return path in _CRITICAL_DIRS or p in _CRITICAL_DIRS or p + "/*" in _CRITICAL_DIRS


def _check_words(words):
    name = words[0].rsplit("/", 1)[-1]
    args = words[1:]
    flags = _short_flags(args)
    targets = _targets(args)
    if name == "rm":
        recursive = flags & {"-r", "-R", "--recursive"}
        if "--no-preserve-root" in flags or (recursive and any(_is_critical(t) for t in targets)):
            return "recursive delete of a system or home directory"
    if name in ("chmod", "chown", "chgrp") and flags & {"-R", "--recursive"}:
        if any(_is_critical(t) for t in targets) or (name == "chmod" and "777" in targets):
            return "recursive permission change on a critical path"
    if name.startswith("mkfs") or name in ("mkswap", "wipefs", "blkdiscard"):
        return "filesystem/disk formatting"
    if name in ("fdisk", "sfdisk", "gdisk", "sgdisk", "parted", "cfdisk"):
        readonly = flags & {"-l", "--list", "-p", "--print", "-s"} or "print" in args
        if not readonly:
            return "disk partitioning"
    if name in ("shutdown", "reboot", "halt", "poweroff"):
        return "host shutdown/reboot"
    if name in ("init", "telinit") and targets[:1] in (["0"], ["6"]):
        return "host shutdown/reboot"
    if name == "systemctl" and any(t in ("reboot", "poweroff", "halt", "kexec", "soft-reboot")
                                   for t in targets):
        return "host shutdown/reboot"
    if name in ("iptables", "ip6tables") and flags & {"-F", "--flush"}:
        return "firewall flush"
    if name == "nft" and "flush" in targets and "ruleset" in targets:
        return "firewall flush"
    if name in ("visudo", "chpasswd", "userdel", "deluser"):
        return "account/sudo modification"
    return None


def dangerous_reason(command):
    """Return a short reason if the command looks destructive, else None."""
    if not isinstance(command, str):
        return None
    for pattern in _RAW_PATTERNS:
        if pattern.search(command):
            return "write to account files or block devices"
    if _SQL_DESTRUCTIVE.search(command) and _DB_CLIENT.search(command):
        return "destructive SQL"
    for words in _segments(command):
        reason = _check_words(words)
        if reason:
            return reason
    return None


def is_dangerous_command(command):
    return dangerous_reason(command) is not None
